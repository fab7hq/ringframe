import json
import subprocess

import pytest

from ringframe import ask, evaluate, sessions, store, workspace
from ringframe.store import LedgerError
from tests.test_ask import compile_, confirm, stage


def ws_for(repo):
    return workspace.resolve(cwd=repo).ensure()


def head(repo):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def commit(repo, files: dict, message="change"):
    for name, text in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if text is None:
            p.unlink()
        else:
            p.write_text(text)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message], check=True)
    return head(repo)


JUDGE = {"host": "claude-code", "model": "claude-sonnet-5", "angle": "coverage", "independence": "sub_agent"}


def intent(brief_sha, items):
    return {"schema": "ringframe.eval-intent/1", "brief_sha256": brief_sha, "judge": {**JUDGE, "angle": "intent"}, "items": items}


def judgement(brief_sha, angle, votes: dict, drift: dict | None = None, **extra):
    return {"schema": "ringframe.eval-judgement/1", "brief_sha256": brief_sha, "judge": {**JUDGE, "angle": angle},
            "votes": [{"item": k, "vote": v, "reason": f"{angle} says {v}"} for k, v in votes.items()],
            "drift": [{"path": p, "finding": "seen", "classification": c} for p, c in (drift or {}).items()], **extra}


def two_asks_and_work(repo):
    """Base commit → Ask A confirmed → Ask B confirmed → work commit touching src/, tests/, docs/."""
    ws = ws_for(repo)
    a = confirm(ws, title="Add uptime endpoint")
    b = confirm(ws, title="Skip the cache", staged=stage(ws, source=b"skip the cache\n", prompt=b"Skip the cache.\n"))
    sha = commit(repo, {"src/uptime.js": "export const uptime = () => 1;\n", "tests/uptime.test.js": "test\n", "docs/notes.md": "unrelated\n"}, "work")
    return ws, a["ask_id"], b["ask_id"], sha


def opened(repo):
    ws, a, b, sha = two_asks_and_work(repo)
    out = evaluate.open_eval(ws)
    return ws, a, b, sha, out, out["brief"]["sha256"]


def test_subject_digests(repo):
    ws = ws_for(repo)
    assert len(evaluate.subject_digest(ws, "git_commit", head(repo))) == 40
    before = evaluate.subject_digest(ws, "worktree", str(repo))
    (repo / "new.txt").write_text("x")
    assert evaluate.subject_digest(ws, "worktree", str(repo)) != before
    (repo / ".gitignore").write_text("ignored.txt\n")
    (repo / "ignored.txt").write_text("y")
    with_ignore = evaluate.subject_digest(ws, "worktree", str(repo))
    (repo / "ignored.txt").write_text("z")
    assert evaluate.subject_digest(ws, "worktree", str(repo)) == with_ignore
    with pytest.raises(LedgerError, match="subject.kind"):
        evaluate.subject_digest(ws, "planet", "mars")


def test_open_refuses_without_an_open_ask(repo):
    ws = ws_for(repo)
    with pytest.raises(LedgerError, match="eval.no_open_ask"):
        evaluate.open_eval(ws)
    out = compile_(ws)
    ask.cancel(ws, out["ask_id"])
    with pytest.raises(LedgerError, match="eval.no_open_ask"):
        evaluate.open_eval(ws)


def test_open_writes_a_facts_only_brief_over_the_open_asks(repo):
    base = head(repo)
    ws, a, b, sha = two_asks_and_work(repo)
    # three plain prompts after Ask B, one observed submission of A's prompt (not counted), one /rf: invocation (not counted)
    sessions.capture(ws, "claude-code", {"session_id": "s9", "prompt": "please also update the docs"})
    sessions.capture(ws, "claude-code", {"session_id": "s9", "prompt": "run the tests"})
    sessions.capture(ws, "claude-code", {"session_id": "s9", "prompt": "/rf:eval"})
    sub = sessions.capture(ws, "claude-code", {"session_id": "s9", "prompt": "Fix the login bug.\n"})
    assert ask.submission_from_capture(ws, "claude-code", "s9", sub["sha256"])["state"] == "observed"
    sessions.capture(ws, "claude-code", {"session_id": "s9", "prompt": "now tidy up"})
    out = evaluate.open_eval(ws)
    assert out["eval_id"].startswith("evl_") and out["basis"]["asks"] == [a, b] and out["basis"]["unrecorded_prompts"] == 3
    assert out["anchor"] == {"kind": "ask_base", "ref": base, "seal_id": None}
    assert out["subject"]["kind"] == "git_commit" and out["subject"]["ref"] == sha
    brief = json.loads((ws.rf_dir / out["brief"]["path"]).read_bytes())
    assert brief["schema"] == "ringframe.eval-brief/1" and [x["order"] for x in brief["asks"]] == [1, 2]
    assert brief["asks"][0]["prompt_path"].endswith("prompt.txt") and brief["asks"][0]["confirmed"] and brief["asks"][0]["submission"] == "observed"
    assert [x["unrecorded_prompts_after"] for x in brief["asks"]] == [0, 3]
    assert [(f["path"], f["status"], f["added"]) for f in brief["changes"]["files"]] == [("docs/notes.md", "added", 1), ("src/uptime.js", "added", 1), ("tests/uptime.test.js", "added", 1)]
    assert brief["previous_evals"] == []
    assert not any(k in json.dumps(brief).replace(str(repo), "") for k in ("npm", "pytest", "package.json", "Makefile"))  # the tmp path itself contains "pytest"
    ev = store.events(ws)[-1]
    assert ev["type"] == "eval.opened" and ev["links"] == [{"rel": "evaluates", "id": a}, {"rel": "evaluates", "id": b}]
    assert store.verify(ws) == []
    listed = evaluate.list_records(ws)
    assert len(listed) == 1 and listed[0]["state"] == "opened" and listed[0]["verdict"] is None


def test_open_on_a_dirty_tree_takes_the_worktree_and_counts_untracked_files(repo):
    ws, a, b, sha = two_asks_and_work(repo)
    (repo / "src" / "uptime.js").write_text("export const uptime = () => 2;\nmore\n")
    (repo / "scratch.txt").write_text("a\nb\n")
    out = evaluate.open_eval(ws)
    assert out["subject"]["kind"] == "worktree"
    brief = json.loads((ws.rf_dir / out["brief"]["path"]).read_bytes())
    files = {f["path"]: f for f in brief["changes"]["files"]}
    assert files["scratch.txt"] == {"path": "scratch.txt", "status": "added", "added": 2, "removed": 0}
    assert files["src/uptime.js"]["added"] == 2 and files["src/uptime.js"]["removed"] == 0  # worktree vs anchor: the base had no file
    assert "subject is the uncommitted worktree" in brief["limitations"]


def test_open_anchors_on_the_last_seal_when_one_exists(repo):
    ws, a, b, sha = two_asks_and_work(repo)
    from ringframe import ids
    store.append(ws, {"schema": store.SCHEMA, "event_id": ids.new_id("evt"), "type": "seal.created", "time": sessions.now(), "id": "sel_old",
                      "actor": {"kind": "human", "id": "local-user"}, "links": [], "data": {
                          "basis": {"asks": ["ask_older"]}, "eval": None, "subject": {"kind": "git_commit", "ref": sha}, "disposition": "accepted",
                          "authority": {"kind": "human", "id": "local-user", "authority": "interactive"},
                          "artifact": {"role": "seal_receipt", "path": "seals/sel_old.json", "bytes": 0, "sha256": "0" * 64}}})
    sha2 = commit(repo, {"src/more.js": "x\n"}, "after seal")
    out = evaluate.open_eval(ws)
    assert out["anchor"] == {"kind": "seal", "ref": sha, "seal_id": "sel_old"}
    brief = json.loads((ws.rf_dir / out["brief"]["path"]).read_bytes())
    assert [f["path"] for f in brief["changes"]["files"]] == ["src/more.js"]
    explicit = evaluate.open_eval(ws, anchor=sha2)
    assert explicit["anchor"]["kind"] == "explicit" and json.loads((ws.rf_dir / explicit["brief"]["path"]).read_bytes())["changes"]["files"] == []
    with pytest.raises(LedgerError, match="eval.anchor_missing"):
        evaluate.open_eval(ws, anchor="0" * 40)


def test_open_outside_git_is_refused_and_missing_anchor_needs_input(tmp_path_factory, repo):
    plain = tmp_path_factory.mktemp("plain")
    ws = workspace.resolve(explicit=plain).ensure()
    compile_(ws)
    with pytest.raises(LedgerError, match="eval.no_git"):
        evaluate.open_eval(ws)
    with pytest.raises(evaluate.NeedsInput, match="eval.anchor_unknown"):
        evaluate._anchor(ws_for(repo), [{"ask_id": "ask_old", "base_commit": None}], None)


def test_close_validates_judgements(repo):
    ws, a, b, sha, out, sha_b = opened(repo)
    eid = out["eval_id"]
    items = [{"id": "i1", "text": "Expose an uptime endpoint", "ask_id": a, "status": "active"}]
    good = lambda angle: judgement(sha_b, angle, {"i1": "yes"})
    with pytest.raises(LedgerError, match="eval.too_few_judges"):
        evaluate.close_eval(ws, eid, intent=intent(sha_b, items), judgements=[good("a"), good("b")])
    with pytest.raises(LedgerError, match="eval.brief_mismatch"):
        evaluate.close_eval(ws, eid, intent=intent("0" * 64, items), judgements=[good("a"), good("b"), good("c")])
    with pytest.raises(LedgerError, match="eval.intent"):
        evaluate.close_eval(ws, eid, intent=intent(sha_b, [{**items[0], "ask_id": "ask_nope"}]), judgements=[good("a"), good("b"), good("c")])
    with pytest.raises(LedgerError, match="eval.judgement"):
        evaluate.close_eval(ws, eid, intent=intent(sha_b, items), judgements=[good("a"), good("b"), judgement(sha_b, "c", {"i1": "maybe"})])
    with pytest.raises(LedgerError, match="no vote for active items"):
        evaluate.close_eval(ws, eid, intent=intent(sha_b, items), judgements=[good("a"), good("b"), judgement(sha_b, "c", {})])
    with pytest.raises(LedgerError, match="eval.judgement"):
        evaluate.close_eval(ws, eid, intent=intent(sha_b, items), judgements=[good("a"), good("b"), judgement(sha_b, "c", {"i1": "yes"}, {"docs/notes.md": "fine"})])
    with pytest.raises(LedgerError, match="eval.judgement"):
        bad = good("c"); bad["judge"] = {"host": "x", "angle": "c", "independence": "telepathy"}
        evaluate.close_eval(ws, eid, intent=intent(sha_b, items), judgements=[good("a"), good("b"), bad])
    with pytest.raises(LedgerError, match="eval.missing"):
        evaluate.close_eval(ws, "evl_nope", intent=intent(sha_b, items), judgements=[good("a"), good("b"), good("c")])
    assert not (ws.rf_dir / f"evals/{eid}/record.json").exists() and store.events(ws)[-1]["type"] == "eval.opened"


def test_close_aligned_with_full_agreement(repo):
    ws, a, b, sha, out, sha_b = opened(repo)
    eid = out["eval_id"]
    items = [{"id": "i1", "text": "Expose an uptime endpoint", "ask_id": a, "status": "active"},
             {"id": "i2", "text": "Cache the result", "ask_id": a, "status": "withdrawn", "by_ask_id": b, "note": "B says skip the cache"},
             {"id": "i3", "text": "Test the endpoint", "ask_id": a, "status": "active"}]
    drift = {"src/uptime.js": "required", "tests/uptime.test.js": "required", "docs/notes.md": "consequence"}
    js = [judgement(sha_b, angle, {"i1": "yes", "i3": "yes"}, drift) for angle in ("coverage", "drift", "adversary")]
    rec = evaluate.close_eval(ws, eid, intent=intent(sha_b, items), judgements=js)
    assert rec["verdict"] == "aligned" and rec["confidence"] == 1.0
    assert [it["id"] for it in rec["items"]] == ["i1", "i3"] and rec["items"][0]["votes"][1] == {"angle": "drift", "vote": "yes", "reason": "drift says yes"}
    assert rec["drift"] == {"omission": [], "commission": [], "unmentioned": [],
                            "paths": [{"path": p, "classification": c, "agreement": 1.0, "mentions": 3, "findings": rec["drift"]["paths"][i]["findings"]} for i, (p, c) in enumerate(sorted(drift.items()))]}
    assert rec["intent"]["items"] == 3 and rec["intent"]["active"] == 2 and len(rec["judgements"]) == 3 and rec["follows"] is None and rec["delta"] is None
    assert rec["basis"]["asks"] == [a, b] and rec["subject"]["sha256_at_close"] == rec["subject"]["sha256"]
    ev = store.events(ws)[-1]
    assert ev["type"] == "eval.completed" and ev["data"]["verdict"] == "aligned" and ev["data"]["confidence"] == 1.0
    assert ev["data"]["items"] == {"active": 2, "met": 2, "omission": 0} and ev["links"][:2] == [{"rel": "evaluates", "id": a}, {"rel": "evaluates", "id": b}]
    assert store.verify(ws) == []
    for name in ("brief.json", "intent.json", "judgement-1.json", "judgement-3.json", "record.json"):
        assert (ws.rf_dir / f"evals/{eid}/{name}").exists()
    listed = evaluate.list_records(ws)[0]
    assert listed["state"] == "completed" and listed["verdict"] == "aligned" and listed["confidence"] == 1.0 and listed["path"] == f"evals/{eid}/record.json"
    with pytest.raises(LedgerError, match="ledger.immutable"):
        evaluate.close_eval(ws, eid, intent=intent(sha_b, items), judgements=js)


def test_close_drifted_reports_disagreement_as_confidence(repo):
    ws, a, b, sha, out, sha_b = opened(repo)
    items = [{"id": "i1", "text": "Expose an uptime endpoint", "ask_id": a, "status": "active"},
             {"id": "i2", "text": "Test the endpoint", "ask_id": a, "status": "active"}]
    js = [judgement(sha_b, "coverage", {"i1": "yes", "i2": "no"}, {"src/uptime.js": "required", "docs/notes.md": "unexplained"}),
          judgement(sha_b, "drift", {"i1": "yes", "i2": "no"}, {"src/uptime.js": "required", "docs/notes.md": "unexplained"}),
          judgement(sha_b, "adversary", {"i1": "no", "i2": "unknown"}, {"src/uptime.js": "required", "docs/notes.md": "consequence"}, basis_notes=["i2 is vague"], commands_run=["git log"])]
    rec = evaluate.close_eval(ws, out["eval_id"], intent=intent(sha_b, items), judgements=js)
    assert rec["verdict"] == "drifted" and rec["confidence"] == 0.67
    assert {it["id"]: (it["majority"], it["agreement"]) for it in rec["items"]} == {"i1": ("yes", 0.67), "i2": ("no", 0.67)}
    assert rec["drift"]["omission"] == ["i2"]
    assert rec["drift"]["commission"] == [{"path": "docs/notes.md", "classification": "unexplained", "agreement": 0.67}]
    assert rec["drift"]["unmentioned"] == ["tests/uptime.test.js"]
    assert any("sub-agents" in l for l in rec["limitations"])


def test_close_incomplete_on_ties_unknowns_or_a_changed_subject(repo):
    ws, a, b, sha, out, sha_b = opened(repo)
    items = [{"id": "i1", "text": "Expose an uptime endpoint", "ask_id": a, "status": "active"}]
    js = [judgement(sha_b, "coverage", {"i1": "yes"}), judgement(sha_b, "drift", {"i1": "no"}), judgement(sha_b, "adversary", {"i1": "unknown"})]
    rec = evaluate.close_eval(ws, out["eval_id"], intent=intent(sha_b, items), judgements=js)
    assert rec["verdict"] == "incomplete" and rec["items"][0]["majority"] == "unknown" and rec["confidence"] == 0.33
    # a worktree subject that changed between open and close is never aligned
    (repo / "src" / "uptime.js").write_text("dirty\n")
    out2 = evaluate.open_eval(ws)
    sha_b2 = out2["brief"]["sha256"]
    assert out2["subject"]["kind"] == "worktree"
    (repo / "src" / "uptime.js").write_text("dirtier\n")
    js2 = [judgement(sha_b2, angle, {"i1": "yes"}) for angle in ("coverage", "drift", "adversary")]
    rec2 = evaluate.close_eval(ws, out2["eval_id"], intent=intent(sha_b2, items), judgements=js2)
    assert rec2["verdict"] == "incomplete" and any(l.startswith("subject.changed") for l in rec2["limitations"])


def test_one_loud_judge_cannot_make_a_path_unanimous(repo):
    ws, a, b, sha, out, sha_b = opened(repo)
    items = [{"id": "i1", "text": "Expose an uptime endpoint", "ask_id": a, "status": "active"}]
    js = [judgement(sha_b, "coverage", {"i1": "yes"}), judgement(sha_b, "drift", {"i1": "yes"}), judgement(sha_b, "adversary", {"i1": "yes"}, {"docs/notes.md": "unexplained"})]
    rec = evaluate.close_eval(ws, out["eval_id"], intent=intent(sha_b, items), judgements=js)
    docs = next(p for p in rec["drift"]["paths"] if p["path"] == "docs/notes.md")
    assert docs == {"path": "docs/notes.md", "classification": "required", "agreement": 0.67, "mentions": 1, "findings": docs["findings"]}
    assert rec["drift"]["commission"] == [] and rec["verdict"] == "aligned" and rec["confidence"] == 0.67
    # two of three flagging it is a finding, at their agreement
    out2 = evaluate.open_eval(ws)
    sha_b2 = out2["brief"]["sha256"]
    js2 = [judgement(sha_b2, "coverage", {"i1": "yes"}, {"docs/notes.md": "unexplained"}), judgement(sha_b2, "drift", {"i1": "yes"}, {"docs/notes.md": "unexplained"}), judgement(sha_b2, "adversary", {"i1": "yes"})]
    rec2 = evaluate.close_eval(ws, out2["eval_id"], intent=intent(sha_b2, items), judgements=js2)
    assert rec2["drift"]["commission"] == [{"path": "docs/notes.md", "classification": "unexplained", "agreement": 0.67}] and rec2["verdict"] == "drifted"


def test_explicit_worktree_subject_diffs_that_root(repo):
    ws, a, b, sha = two_asks_and_work(repo)
    (repo / "scratch.txt").write_text("a\n")
    out = evaluate.open_eval(ws, subject_kind="worktree", subject_ref=str(repo))
    brief = json.loads((ws.rf_dir / out["brief"]["path"]).read_bytes())
    assert "scratch.txt" in [f["path"] for f in brief["changes"]["files"]] and out["subject"]["kind"] == "worktree"
    with pytest.raises(LedgerError, match="subject.kind"):
        evaluate.open_eval(ws, subject_kind="worktree")


def test_shared_context_judges_are_recorded_as_a_limitation(repo):
    ws, a, b, sha, out, sha_b = opened(repo)
    items = [{"id": "i1", "text": "Expose an uptime endpoint", "ask_id": a, "status": "active"}]
    js = [judgement(sha_b, angle, {"i1": "yes"}) for angle in ("coverage", "drift", "adversary")]
    for j in js:
        j["judge"]["independence"] = "shared_context"
    rec = evaluate.close_eval(ws, out["eval_id"], intent=intent(sha_b, items), judgements=js)
    assert rec["verdict"] == "aligned" and any("shared one context" in l for l in rec["limitations"])


def test_second_eval_follows_the_first_and_reports_the_delta(repo):
    ws, a, b, sha, out, sha_b = opened(repo)
    items = [{"id": "i1", "text": "Expose an uptime endpoint", "ask_id": a, "status": "active"},
             {"id": "i2", "text": "Test the endpoint", "ask_id": a, "status": "active"}]
    first = evaluate.close_eval(ws, out["eval_id"], intent=intent(sha_b, items),
                           judgements=[judgement(sha_b, ang, {"i1": "yes", "i2": "no"}, {"docs/notes.md": "unexplained"}) for ang in ("coverage", "drift", "adversary")])
    assert first["verdict"] == "drifted"
    commit(repo, {"tests/uptime.test.js": "real test\n", "docs/notes.md": None}, "fix")
    out2 = evaluate.open_eval(ws)
    sha_b2 = out2["brief"]["sha256"]
    brief2 = json.loads((ws.rf_dir / out2["brief"]["path"]).read_bytes())
    assert brief2["previous_evals"] == [{"eval_id": first["eval_id"], "verdict": "drifted", "confidence": 1.0, "time": first["time"]}]
    assert [f["path"] for f in brief2["changes"]["files"]] == ["src/uptime.js", "tests/uptime.test.js"]  # docs/notes.md no longer differs from the anchor
    # the second intent judge numbers the items differently; matching is by text
    items2 = [{"id": "x1", "text": "Test the endpoint", "ask_id": a, "status": "active"}, {"id": "x2", "text": "Expose an uptime endpoint", "ask_id": a, "status": "active"}]
    second = evaluate.close_eval(ws, out2["eval_id"], intent=intent(sha_b2, items2),
                            judgements=[judgement(sha_b2, ang, {"x1": "yes", "x2": "yes"}, {"src/uptime.js": "required", "tests/uptime.test.js": "required"}) for ang in ("coverage", "drift", "adversary")])
    assert second["verdict"] == "aligned" and second["follows"] == first["eval_id"]
    assert second["delta"]["closed"] == ["test the endpoint"] and second["delta"]["opened"] == []
    assert second["delta"]["commission_removed"] == ["docs/notes.md"] and second["delta"]["commission_added"] == []
    assert {"rel": "supersedes", "id": first["eval_id"]} in store.events(ws)[-1]["links"]
    assert [r["eval_id"] for r in evaluate.list_records(ws)] == [first["eval_id"], second["eval_id"]]
    assert evaluate.latest_for(ws, [a])["eval_id"] == second["eval_id"] and evaluate.latest_for(ws, ["ask_other"]) is None
