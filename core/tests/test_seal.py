import json
import subprocess

import pytest

from ringframe import evaluate, seal, store, workspace
from ringframe.seal import Refused
from tests.test_eval import definition, head


def aligned_eval(repo, kind="git_commit"):
    ws = workspace.resolve(cwd=repo).ensure()
    ref = head(repo) if kind == "git_commit" else str(repo)
    frozen = evaluate.freeze(ws, subject_kind=kind, subject_ref=ref, definition=definition())
    rec = evaluate.run(ws, frozen["eval_id"], observations=[{"requirement": "R2", "source": "human:local-user", "scope": "s", "time": "t", "statement": "ok", "outcome": "pass", "limitations": []}])
    return ws, rec


def test_create_accepted_receipt(repo):
    ws, rec = aligned_eval(repo)
    receipt = seal.create(ws, rec["eval_id"], "accepted")
    assert receipt["seal_id"].startswith("sel_") and receipt["eval"]["verdict"] == "aligned" and receipt["actor"]["authority"] == "interactive"
    ev = store.events(ws)[-1]
    assert ev["type"] == "seal.created" and ev["links"] == [{"rel": "seals", "id": rec["eval_id"]}]
    assert store.verify(ws) == []
    assert seal.check(ws, receipt["seal_id"])["fresh"] is True


def test_refusals_write_refused_event(repo):
    ws, rec = aligned_eval(repo)
    with pytest.raises(Refused) as e:
        seal.create(ws, "evl_missing", "accepted")
    assert e.value.codes == ["seal.eval_missing"]
    with pytest.raises(Refused) as e:
        seal.create(ws, rec["eval_id"], "accepted", actor={"kind": "agent", "id": "ci", "authority": "preauthorized"})
    assert e.value.codes == ["seal.authority_missing"]
    assert [ev["type"] for ev in store.events(ws)][-2:] == ["seal.refused", "seal.refused"]
    assert not list((ws.rf_dir / "seals").iterdir())


def test_preauthorized_agent_can_seal_within_grant(repo):
    ws, rec = aligned_eval(repo)
    (ws.rf_dir / "authorizations").mkdir()
    (ws.rf_dir / "authorizations" / "ci.json").write_text(json.dumps({
        "schema": "ringframe.authorization/1", "actor": "agent:ci", "granted_by": "human:owner", "time": "t",
        "allowed": {"dispositions": ["accepted"], "eval_verdicts": ["aligned"], "subject_kinds": ["git_commit"]},
        "expires": "2999-01-01T00:00:00Z"}))
    r = seal.create(ws, rec["eval_id"], "accepted", actor={"kind": "agent", "id": "ci", "authority": "preauthorized"})
    assert r["actor"]["authority"] == "preauthorized:authorizations/ci.json"
    with pytest.raises(Refused) as e:
        seal.create(ws, rec["eval_id"], "rejected", actor={"kind": "agent", "id": "ci", "authority": "preauthorized"})
    assert e.value.codes == ["seal.authority_missing"]


def test_subject_changed_and_stale_and_duplicate(repo):
    ws, rec = aligned_eval(repo, kind="worktree")
    seal.create(ws, rec["eval_id"], "deferred")
    with pytest.raises(Refused) as e:
        seal.create(ws, rec["eval_id"], "deferred")
    assert e.value.codes == ["seal.duplicate"]
    (repo / "README.md").write_text("changed\n")
    with pytest.raises(Refused) as e:
        seal.create(ws, rec["eval_id"], "accepted")
    assert e.value.codes == ["seal.subject_changed"]
    assert seal.check(ws, store.events(ws)[-3]["id"])["fresh"] is False


def test_stale_eval_is_refused(repo, monkeypatch):
    ws, rec = aligned_eval(repo)
    import datetime as dt
    monkeypatch.setattr(seal, "_now", lambda: dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2))
    with pytest.raises(Refused) as e:
        seal.create(ws, rec["eval_id"], "accepted")
    assert e.value.codes == ["seal.stale"]


def test_verdict_conflict_requires_acknowledgement(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    frozen = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=definition())
    rec = evaluate.run(ws, frozen["eval_id"])  # R2 uncovered -> incomplete
    with pytest.raises(Refused) as e:
        seal.create(ws, rec["eval_id"], "accepted")
    assert e.value.codes == ["seal.verdict_conflict"]
    r = seal.create(ws, rec["eval_id"], "accepted", acknowledge=["shipping without human review"])
    assert r["eval"]["verdict"] == "incomplete" and r["acknowledged"] == ["shipping without human review"]
    assert seal.create(ws, rec["eval_id"], "rejected")["disposition"] == "rejected"  # no ack needed
