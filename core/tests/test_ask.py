import json

import pytest

from ringframe import ask, sessions, store, workspace
from ringframe.ask import NeedsInput
from ringframe.store import LedgerError

HOST = {"name": "claude-code", "version": "2.1.260", "surface": "native-tui", "session_ref": "s1"}
CLS = {"task": ["plan"], "result": "plan", "interaction": "approval_gated", "horizon": "session", "effects": ["read"]}
ROUTE = {"fits": "bounded", "alternatives": [{"capability": "native_direct", "reason": "no review"}], "continuation": "plan review", "effects": "reads", "gaps": []}


def stage(ws, source=b"fix the login bug\n", prompt=b"Fix the login bug.\n"):
    d = ws.rf_dir / "tmp" / "stage-1"
    d.mkdir(parents=True)
    (d / "source.txt").write_bytes(source)
    (d / "prompt.txt").write_bytes(prompt)
    return d


def confirm(ws, **kw):
    args = dict(staged=stage(ws), title="Login fix", capability="native_plan", classification=CLS, route=ROUTE, host=HOST)
    args.update(kw)
    return ask.confirm(ws, **args)


def test_confirm_publishes_two_artifacts_and_one_event(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    sessions.capture(ws, "claude-code", {"session_id": "s1", "prompt": "/rf:ask fix the login bug"})
    out = confirm(ws)
    assert out["ask_id"].startswith("ask_") and out["delivery_mode"] == "native_dispatch" and out["source_verified"] == "exact"
    assert (ws.rf_dir / out["prompt"]["path"]).read_bytes() == b"Fix the login bug.\n"
    assert not (ws.rf_dir / "tmp" / "stage-1").exists()
    ev, = store.events(ws)
    assert ev["type"] == "ask.confirmed" and ev["id"] == out["ask_id"]
    assert ev["data"]["host"]["profile_id"] == "claude-code@2.1" and ev["data"]["host"]["workspace"]["rule"] == "git_toplevel"
    assert store.verify(ws) == []


def test_confirm_resolves_session_and_version_from_capture(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    sessions.capture(ws, "claude-code", {"session_id": "hook-session", "prompt": "/rf:ask fix the login bug"}, host_version="2.1.263 (Claude Code)")
    out = confirm(ws, host={"name": "claude-code", "surface": "native-tui"})
    assert out["source_verified"] == "exact"
    host = store.events(ws)[0]["data"]["host"]
    assert host["session_ref"] == "hook-session" and host["session_ref_source"] == "capture"
    assert host["version"] == "2.1.263 (Claude Code)" and host["version_source"] == "capture"
    assert host["profile_id"] == "claude-code@2.1"
    assert ask.delivery_from_hook(ws, hook(session="hook-session"))["state"] == "native_accepted"


def test_confirm_without_capture_is_unverified(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = confirm(ws)
    assert out["source_verified"] == "unverified"
    assert store.events(ws)[0]["data"]["source_verified"] == "unverified"


def test_confirm_rejects_bad_staging_and_unknown_capability(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    d = stage(ws)
    (d / "extra").write_text("x")
    with pytest.raises(LedgerError, match="ask.staged_dir"):
        ask.confirm(ws, staged=d, title="t", capability="native_plan", classification=CLS, route=ROUTE, host=HOST)
    (d / "extra").unlink()
    with pytest.raises(LedgerError, match="ask.capability"):
        ask.confirm(ws, staged=d, title="t", capability="native_goal", classification=CLS, route=ROUTE, host=HOST)
    assert store.events(ws) == [] and (d / "source.txt").exists()


def test_direct_route_with_effects_needs_explicit_request(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    with pytest.raises(LedgerError, match="ask.route_policy"):
        confirm(ws, capability="native_direct", classification={**CLS, "effects": ["write"]})
    assert store.events(ws) == [] and not list((ws.rf_dir / "asks").iterdir())
    out = ask.confirm(ws, staged=ws.rf_dir / "tmp" / "stage-1", title="Login fix", capability="native_direct",  # staging survived the refusal
                      classification={**CLS, "effects": ["write"]}, route={**ROUTE, "explicit_direct_request": True}, host=HOST)
    assert out["delivery_mode"] == "native_dispatch"
    (ws.rf_dir / "tmp" / "stage-2").mkdir()
    (ws.rf_dir / "tmp" / "stage-2" / "source.txt").write_bytes(b"what does auth.ts do?")
    (ws.rf_dir / "tmp" / "stage-2" / "prompt.txt").write_bytes(b"Explain auth.ts.")
    ask.confirm(ws, staged=ws.rf_dir / "tmp" / "stage-2", title="Q", capability="native_direct", classification={**CLS, "task": ["question"], "result": "answer", "effects": ["read"]}, route=ROUTE, host=HOST)


def test_invalid_classification_publishes_nothing(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    bad = {**CLS, "task": ["add-endpoint"]}
    with pytest.raises(LedgerError, match="classification.task"):
        confirm(ws, classification=bad)
    assert not list((ws.rf_dir / "asks").iterdir()) and store.events(ws) == [] and store.verify(ws) == []
    assert (ws.rf_dir / "tmp" / "stage-1" / "source.txt").exists()  # staging survives for a retry


def test_hyphenated_vocabulary_is_accepted(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = confirm(ws, classification={**CLS, "interaction": "approval-gated", "horizon": "one-turn"})
    c = store.events(ws)[0]["data"]["classification"]
    assert c["interaction"] == "approval_gated" and c["horizon"] == "one_turn" and store.verify(ws) == []


def test_unknown_host_falls_back_to_handoff(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = confirm(ws, host={"name": "cursor", "version": "1.0", "surface": "cli", "session_ref": None}, capability="human_handoff")
    assert out["delivery_mode"] == "human_handoff"
    assert "qualification" in " ".join(store.events(ws)[0]["data"]["limitations"]).lower()


def test_cancel_keeps_both_artifacts(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = ask.cancel(ws, staged=stage(ws), title="t", capability="native_plan", classification=CLS, route=ROUTE, host=HOST, reason="changed mind")
    ev, = store.events(ws)
    assert ev["type"] == "ask.cancelled" and ev["data"]["reason"] == "changed mind" and "delivery_mode" not in ev["data"]
    assert (ws.rf_dir / out["source"]["path"]).exists() and (ws.rf_dir / out["prompt"]["path"]).exists()


def hook(session="s1", error=False, tool="EnterPlanMode"):
    return {"hook_event_name": "PostToolUse", "session_id": session, "tool_name": tool, "tool_use_id": "toolu_1",
            "tool_input": {}, "tool_response": {"error": "denied"} if error else {"ok": True}}


def test_delivery_from_hook_records_native_accepted_once(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = confirm(ws)
    rec = ask.delivery_from_hook(ws, hook())
    assert rec["state"] == "native_accepted" and rec["ask_id"] == out["ask_id"]
    ev = store.events(ws)[-1]
    assert ev["type"] == "ask.delivery" and ev["data"]["receipt"]["tool_use_id"] == "toolu_1"
    assert ev["data"]["receipt"]["captured_by"] == "hook:PostToolUse" and ev["data"]["qualification"]["id"] == "ringframe-ask-plan-q04"
    assert ask.delivery_from_hook(ws, hook()) is None  # already delivered: skip, log
    skipped = (ws.rf_dir / "sessions/claude-code/s1/delivery-skipped.jsonl").read_text()
    assert "no_candidate" in skipped
    assert len([e for e in store.events(ws) if e["type"] == "ask.delivery"]) == 1


def test_delivery_from_hook_error_records_failed(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    confirm(ws)
    assert ask.delivery_from_hook(ws, hook(error=True))["state"] == "delivery_failed"


def test_delivery_from_hook_ignores_other_sessions_tools_and_ambiguity(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    confirm(ws)
    assert ask.delivery_from_hook(ws, hook(session="other")) is None
    assert ask.delivery_from_hook(ws, hook(tool="Write")) is None
    (ws.rf_dir / "tmp" / "stage-1").mkdir()
    (ws.rf_dir / "tmp" / "stage-1" / "source.txt").write_bytes(b"a")
    (ws.rf_dir / "tmp" / "stage-1" / "prompt.txt").write_bytes(b"b")
    ask.confirm(ws, staged=ws.rf_dir / "tmp" / "stage-1", title="second", capability="native_plan", classification=CLS, route=ROUTE, host=HOST)
    assert ask.delivery_from_hook(ws, hook()) is None
    assert "ambiguous" in (ws.rf_dir / "sessions/claude-code/s1/delivery-skipped.jsonl").read_text()


def test_handoff_emits_text_and_records_once(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = confirm(ws)
    text, rec = ask.delivery_handoff(ws, out["ask_id"])
    assert str(ws.rf_dir / out["prompt"]["path"]) in text and "active Claude Code TUI" in text
    assert rec["state"] == "handoff_ready" and store.events(ws)[-1]["data"]["submission"] == "unobserved"
    with pytest.raises(LedgerError, match="delivery.duplicate"):
        ask.delivery_state(ws, out["ask_id"], "unavailable", "x")


def test_show_and_resolve(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    a = confirm(ws)
    shown = ask.show(ws, ask_id=a["ask_id"])
    assert shown["title"] == "Login fix" and shown["delivery"] is None and shown["prompt_path"].endswith("prompt.txt")
    assert ask.show(ws, session="s1")["ask_id"] == a["ask_id"]
    assert ask.show(ws, ask_id="login")["ask_id"] == a["ask_id"]  # unique title substring
    assert ask.show(ws)["ask_id"] == a["ask_id"]  # unique in workspace
    (ws.rf_dir / "tmp" / "stage-2").mkdir()
    (ws.rf_dir / "tmp" / "stage-2" / "source.txt").write_bytes(b"a")
    (ws.rf_dir / "tmp" / "stage-2" / "prompt.txt").write_bytes(b"b")
    b = ask.confirm(ws, staged=ws.rf_dir / "tmp" / "stage-2", title="Logout", capability="native_direct", classification=CLS, route=ROUTE, host={**HOST, "session_ref": "s2"})
    with pytest.raises(NeedsInput) as e:
        ask.show(ws)
    assert {c["id"] for c in e.value.candidates} == {a["ask_id"], b["ask_id"]}
    with pytest.raises(NeedsInput):
        ask.show(ws, ask_id="Log")
    cands = ask.resolve(ws, session="s2")
    assert [c["id"] for c in cands["candidates"]] == [b["ask_id"]] and cands["rule_applied"] == "same_session"
