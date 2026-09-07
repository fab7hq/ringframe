import json

import pytest

from ringframe import ask, evaluate, seal, store
from ringframe.seal import Refused
from tests.test_eval import commit, intent, judgement, opened


def judged(repo, votes=("yes", "yes", "yes")):
    ws, a, b, sha, out, sha_b = opened(repo)
    items = [{"id": "i1", "text": "Expose an uptime endpoint", "ask_id": a, "status": "active"}]
    rec = evaluate.close_eval(ws, out["eval_id"], intent=intent(sha_b, items),
                         judgements=[judgement(sha_b, ang, {"i1": v}) for ang, v in zip(("coverage", "drift", "adversary"), votes)])
    return ws, a, b, rec


def test_seal_closes_the_open_asks_and_records_the_eval_as_a_fact(repo):
    ws, a, b, rec = judged(repo)
    receipt = seal.create(ws, "accepted", note="good enough for the demo")
    assert receipt["seal_id"].startswith("sel_") and receipt["basis"] == {"asks": [a, b]} and receipt["disposition"] == "accepted"
    assert receipt["eval"]["eval_id"] == rec["eval_id"] and receipt["eval"]["verdict"] == "aligned" and receipt["eval"]["confidence"] == 1.0
    assert receipt["eval"]["subject_matches"] is True and receipt["note"] == "good enough for the demo" and receipt["authority"]["authority"] == "interactive"
    assert [x["title"] for x in receipt["asks"]] == ["Add uptime endpoint", "Skip the cache"]
    ev = store.events(ws)[-1]
    assert ev["type"] == "seal.created" and ev["links"] == [{"rel": "seals", "id": a}, {"rel": "seals", "id": b}, {"rel": "seals", "id": rec["eval_id"]}]
    assert store.verify(ws) == []
    assert ask.open_asks(ws) == [] and {x["state"] for x in ask.list_asks(ws)} == {"sealed"}
    chk = seal.check(ws, receipt["seal_id"])
    assert chk["fresh"] is True and chk["subject_matches"] is True and chk["eval"]["verdict"] == "aligned" and chk["basis"] == {"asks": [a, b]}


def test_a_bad_verdict_never_blocks_the_seal(repo):
    ws, a, b, rec = judged(repo, votes=("no", "no", "unknown"))
    assert rec["verdict"] == "drifted"
    receipt = seal.create(ws, "accepted")
    assert receipt["eval"]["verdict"] == "drifted" and receipt["disposition"] == "accepted"
    assert store.events(ws)[-1]["type"] == "seal.created"


def test_seal_without_an_eval_records_the_gap(repo):
    ws, a, b, sha, out, sha_b = opened(repo)  # opened but never closed
    receipt = seal.create(ws, "deferred")
    assert receipt["eval"] is None and any("no Eval" in l for l in receipt["limitations"])
    assert seal.check(ws, receipt["seal_id"])["eval"] is None


def test_subject_change_after_the_eval_is_a_recorded_fact_not_a_refusal(repo):
    ws, a, b, rec = judged(repo)
    commit(repo, {"src/uptime.js": "changed after eval\n"}, "later")
    receipt = seal.create(ws, "accepted")
    assert receipt["eval"]["subject_matches"] is False and any("subject changed" in l for l in receipt["limitations"])
    assert receipt["subject"]["ref"] != rec["subject"]["ref"]
    chk = seal.check(ws, receipt["seal_id"])
    assert chk["fresh"] is True and chk["subject_matches"] is True  # the sealed commit's tree is immutable; later commits do not touch it


def test_refusals_no_open_ask_and_missing_eval(repo):
    ws, a, b, rec = judged(repo)
    with pytest.raises(Refused) as e:
        seal.create(ws, "accepted", eval_id="evl_missing")
    assert e.value.codes == ["seal.eval_missing"]
    seal.create(ws, "accepted", eval_id=rec["eval_id"])["eval"]["eval_id"] == rec["eval_id"]
    # a later basis cannot seal against an Eval of the earlier, closed Asks
    from tests.test_ask import confirm
    c = confirm(ws, title="Third")
    with pytest.raises(Refused) as e:
        seal.create(ws, "accepted", eval_id=rec["eval_id"])
    assert e.value.codes == ["seal.eval_unrelated"]
    seal.create(ws, "abandoned")
    assert ask.list_asks(ws)[-1]["state"] == "sealed" and c["ask_id"] == ask.list_asks(ws)[-1]["ask_id"]
    with pytest.raises(Refused) as e:
        seal.create(ws, "accepted")
    assert e.value.codes == ["seal.no_open_ask"]
    assert [ev["type"] for ev in store.events(ws)][-2:] == ["seal.created", "seal.refused"]
    assert len(list((ws.rf_dir / "seals").iterdir())) == 2


def test_non_human_actor_needs_a_grant(repo):
    ws, a, b, rec = judged(repo)
    with pytest.raises(Refused) as e:
        seal.create(ws, "accepted", actor={"kind": "agent", "id": "ci", "authority": "preauthorized"})
    assert e.value.codes == ["seal.authority_missing"]
    (ws.rf_dir / "authorizations").mkdir()
    (ws.rf_dir / "authorizations" / "ci.json").write_text(json.dumps({
        "schema": "ringframe.authorization/1", "actor": "agent:ci", "granted_by": "human:owner", "time": "t",
        "allowed": {"dispositions": ["accepted"], "subject_kinds": ["git_commit"]}, "expires": "2999-01-01T00:00:00Z"}))
    with pytest.raises(Refused) as e:
        seal.create(ws, "rejected", actor={"kind": "agent", "id": "ci", "authority": "preauthorized"})
    assert e.value.codes == ["seal.authority_missing"]
    r = seal.create(ws, "accepted", actor={"kind": "agent", "id": "ci", "authority": "preauthorized"})
    assert r["authority"]["authority"] == "preauthorized:authorizations/ci.json"


def test_check_detects_tampering(repo):
    ws, a, b, rec = judged(repo)
    receipt = seal.create(ws, "accepted")
    p = ws.rf_dir / f"seals/{receipt['seal_id']}.json"
    import os
    os.chmod(p, 0o600)
    p.write_text(p.read_text().replace("accepted", "rejected"))
    chk = seal.check(ws, receipt["seal_id"])
    assert chk["fresh"] is False and chk["codes"] == ["seal.receipt_tampered"]
    assert seal.check(ws, "sel_nope") == {"seal_id": "sel_nope", "fresh": False, "codes": ["seal.receipt_missing"]}
