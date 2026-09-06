import json
import time

from ringframe import sessions, workspace


def payload(prompt, session="s1"):
    return {"hook_event_name": "UserPromptSubmit", "session_id": session, "cwd": "/w", "permission_mode": "default", "prompt": prompt}


def test_capture_stores_only_rf_invocations(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    assert sessions.capture(ws, "claude-code", payload("hello")) is None
    rec = sessions.capture(ws, "claude-code", payload("/rf:ask fix the login bug"))
    assert rec["sha256"] and rec["bytes"] == len("/rf:ask fix the login bug")
    stored = (ws.rf_dir / "sessions/claude-code/s1/prompts.jsonl").read_text().splitlines()
    assert len(stored) == 1 and json.loads(stored[0])["prompt"] == "/rf:ask fix the login bug"


def test_find_invocation_matches_argument_bytes(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    sessions.capture(ws, "claude-code", payload("/rf:ask fix the login bug"))
    assert sessions.source_verified(ws, "claude-code", "s1", b"fix the login bug\n") == ("exact", None)
    assert sessions.source_verified(ws, "claude-code", "s1", b"fix login") == ("unverified", "mismatch")
    assert sessions.source_verified(ws, "claude-code", "nope", b"x") == ("unverified", "no_capture")
    assert sessions.source_verified(ws, "claude-code", None, b"x") == ("unverified", "no_session_ref")


def test_capture_records_host_version_and_resolves_session(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    rec = sessions.capture(ws, "claude-code", payload("/rf:ask fix the login bug", "sA"), host_version="2.1.263 (Claude Code)\n")
    assert rec["host_version"] == "2.1.263 (Claude Code)"
    assert sessions.resolve_session(ws, "claude-code", b"fix the login bug\n") == {"session_ref": "sA", "host_version": "2.1.263 (Claude Code)"}
    assert sessions.resolve_session(ws, "claude-code", b"something else") is None
    sessions.capture(ws, "claude-code", payload("/rf:ask fix the login bug", "sB"))
    assert sessions.resolve_session(ws, "claude-code", b"fix the login bug") is None  # ambiguous


def test_prune_removes_old_sessions(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    sessions.capture(ws, "claude-code", payload("/rf:ask a", "old"))
    sessions.capture(ws, "claude-code", payload("/rf:ask b", "new"))
    import os
    old = ws.rf_dir / "sessions/claude-code/old"
    t = time.time() - 10 * 86400
    for p in [old, *old.iterdir()]:
        os.utime(p, (t, t))
    removed = sessions.prune(ws, "7d")
    assert removed == ["claude-code/old"] and not old.exists()
    assert sessions.parse_duration("36h") == 36 * 3600
