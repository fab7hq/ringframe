import json

import pytest

from ringframe import ask, sessions, store, workspace, ids
from ringframe.ask import NeedsInput
from ringframe.store import LedgerError

HOST = {"name": "claude-code", "version": "2.1.260", "surface": "native-tui", "session_ref": "s1"}
CLS = {"task": ["plan"], "result": "plan", "interaction": "approval_gated", "horizon": "session", "effects": ["read"]}
ROUTE = {"fits": "bounded", "alternatives": [{"capability": "native_direct", "reason": "no review"}], "continuation": "plan review", "effects": "reads", "gaps": []}


def stage(ws, source=b"fix the login bug\n", prompt=b"Fix the login bug.\n"):
    d = ws.rf_dir / "tmp" / "stage-1"
    n = 1
    while d.exists():
        n += 1
        d = ws.rf_dir / "tmp" / f"stage-{n}"
    d.mkdir(parents=True)
    (d / "source.txt").write_bytes(source)
    (d / "prompt.txt").write_bytes(prompt)
    return d


def compile_(ws, **kw):
    args = dict(title="Login fix", capability="native_plan", classification=CLS, route=ROUTE, host=HOST)
    args.update(kw)
    if "staged" not in args:
        args["staged"] = stage(ws)
    return ask.compile(ws, **args)


def confirm(ws, **kw):
    out = compile_(ws, **kw)
    ask.confirm(ws, out["ask_id"])
    return out


def test_compile_publishes_two_artifacts_and_one_event(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    sessions.capture(ws, "claude-code", {"session_id": "s1", "prompt": "/rf:ask fix the login bug"})
    out = compile_(ws)
    assert out["ask_id"].startswith("ask_") and out["delivery_mode"] == "native_dispatch" and out["source_verified"] == "exact"
    assert (ws.rf_dir / out["prompt"]["path"]).read_bytes() == b"Fix the login bug.\n"
    assert not (ws.rf_dir / "tmp" / "stage-1").exists()
    ev, = store.events(ws)
    assert ev["type"] == "ask.compiled" and ev["id"] == out["ask_id"]
    assert ev["data"]["host"]["profile_id"] == "claude-code@2.1" and ev["data"]["host"]["workspace"]["rule"] == "git_toplevel"
    assert store.verify(ws) == []
    assert ask.show(ws)["outcome"] == "compiled" and ask.show(ws)["submission"] == "unobserved"


def test_confirm_and_cancel_are_appended_graded_events(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = compile_(ws)
    rec = ask.confirm(ws, out["ask_id"])
    assert rec["confirmation"] == {"observed_by": "skill", "surface": None}  # no capture -> unknown profile -> no surface claimed
    with pytest.raises(LedgerError, match="ask.already_confirmed"):
        ask.confirm(ws, out["ask_id"])
    later = ask.cancel(ws, out["ask_id"], reason="changed my mind", attributed=True)
    assert later["cancellation"] == {"attributed_by": "human:local-user"}
    assert [e["type"] for e in store.events(ws)] == ["ask.compiled", "ask.confirmed", "ask.cancelled"]
    assert ask.show(ws)["outcome"] == "cancelled" and store.verify(ws) == []
    with pytest.raises(LedgerError, match="ask.not_compiled"):
        ask.confirm(ws, "ask_nope")


def test_submission_observed_from_capture_and_attributed_by_human(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = compile_(ws, host={"name": "codex", "surface": "native-tui"}, capability="human_handoff")
    other = compile_(ws, staged=stage(ws, prompt=b"Something else.\n"), title="Other", host={"name": "codex", "surface": "native-tui"}, capability="human_handoff")
    # the person pastes the exact prompt; the hook captures its digest
    rec = sessions.capture(ws, "codex", {"session_id": "c1", "prompt": "Fix the login bug.\n"})
    sub = ask.submission_from_capture(ws, "codex", "c1", rec["sha256"])
    assert sub["ask_id"] == out["ask_id"] and sub["state"] == "observed" and sub["observed_by"] == "hook:UserPromptSubmit"
    assert sub["match"] == "exact"
    assert ask.submission_from_capture(ws, "codex", "c1", rec["sha256"]) is None  # once only
    # composers drop the trailing newline of a pasted file; that is still the same prompt
    pasted = sessions.capture(ws, "codex", {"session_id": "c1", "prompt": "Something else."})
    sub2 = ask.submission_from_capture(ws, "codex", "c1", pasted["sha256"])
    assert sub2["ask_id"] == other["ask_id"] and sub2["match"] == "trailing_newline_dropped"
    assert ask.show(ws, ask_id=other["ask_id"])["submission"] == "observed"
    third = compile_(ws, staged=stage(ws, prompt=b"Third.\n"), title="Third", host={"name": "codex", "surface": "native-tui"}, capability="human_handoff")
    assert ask.submission_from_capture(ws, "codex", "c1", "f" * 64) is None  # no match
    assert ask.show(ws, ask_id=out["ask_id"])["submission"] == "observed"
    att = ask.submitted(ws, third["ask_id"], as_modified=True)
    assert att["state"] == "attributed" and att["as_modified"] is True and ask.show(ws, ask_id=third["ask_id"])["submission"] == "attributed"
    assert store.verify(ws) == []


def test_prompt_text_for_copy(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = compile_(ws)
    assert ask.prompt_text(ws, out["ask_id"]) == "Fix the login bug.\n"


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


def test_compile_without_capture_is_unverified(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = compile_(ws)
    assert out["source_verified"] == "unverified"
    assert store.events(ws)[0]["data"]["source_verified"] == "unverified"


def test_confirm_rejects_bad_staging_and_unknown_capability(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    d = stage(ws)
    (d / "extra").write_text("x")
    with pytest.raises(LedgerError, match="ask.staged_dir"):
        ask.compile(ws, staged=d, title="t", capability="native_plan", classification=CLS, route=ROUTE, host=HOST)
    (d / "extra").unlink()
    with pytest.raises(LedgerError, match="ask.capability"):
        ask.compile(ws, staged=d, title="t", capability="native_review", classification=CLS, route=ROUTE, host=HOST)
    assert store.events(ws) == [] and (d / "source.txt").exists()


def test_direct_route_with_effects_needs_explicit_request(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    with pytest.raises(LedgerError, match="ask.route_policy"):
        confirm(ws, capability="native_direct", classification={**CLS, "effects": ["write"]})
    assert store.events(ws) == [] and not list((ws.rf_dir / "asks").iterdir())
    out = ask.compile(ws, staged=ws.rf_dir / "tmp" / "stage-1", title="Login fix", capability="native_direct",  # staging survived the refusal
                      classification={**CLS, "effects": ["write"]}, route={**ROUTE, "explicit_direct_request": True}, host=HOST)
    assert out["delivery_mode"] == "native_dispatch"
    (ws.rf_dir / "tmp" / "stage-2").mkdir()
    (ws.rf_dir / "tmp" / "stage-2" / "source.txt").write_bytes(b"what does auth.ts do?")
    (ws.rf_dir / "tmp" / "stage-2" / "prompt.txt").write_bytes(b"Explain auth.ts.")
    ask.compile(ws, staged=ws.rf_dir / "tmp" / "stage-2", title="Q", capability="native_direct", classification={**CLS, "task": ["question"], "result": "answer", "effects": ["read"]}, route=ROUTE, host=HOST)


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


def test_cancel_after_compile_keeps_both_artifacts(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = compile_(ws)
    rec = ask.cancel(ws, out["ask_id"], reason="changed mind")
    events = store.events(ws)
    assert [e["type"] for e in events] == ["ask.compiled", "ask.cancelled"] and events[1]["data"]["reason"] == "changed mind"
    assert rec["cancellation"] == {"observed_by": "skill"}
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
    ask.compile(ws, staged=ws.rf_dir / "tmp" / "stage-1", title="second", capability="native_plan", classification=CLS, route=ROUTE, host=HOST)
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
    b = ask.compile(ws, staged=ws.rf_dir / "tmp" / "stage-2", title="Logout", capability="native_direct", classification=CLS, route=ROUTE, host={**HOST, "session_ref": "s2"})
    with pytest.raises(NeedsInput) as e:
        ask.show(ws)
    assert {c["id"] for c in e.value.candidates} == {a["ask_id"], b["ask_id"]}
    with pytest.raises(NeedsInput):
        ask.show(ws, ask_id="Log")
    cands = ask.resolve(ws, session="s2")
    assert [c["id"] for c in cands["candidates"]] == [b["ask_id"]] and cands["rule_applied"] == "same_session"


def test_codex_handoff_prompt_prefix_and_length_policy(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    host = {"name": "codex", "version": "codex-cli 0.153.1", "surface": "native-tui"}
    out = compile_(ws, staged=stage(ws, prompt=b"/goal Keep the checkout p95 under 800 ms.\n"), capability="native_goal", host=host,
                   classification={**CLS, "result": "continuing_objective", "horizon": "persistent"})
    assert out["delivery_mode"] == "human_handoff"
    with pytest.raises(LedgerError, match="ask.prompt_prefix"):
        compile_(ws, staged=stage(ws, prompt=b"Keep the checkout fast.\n"), capability="native_goal", host=host, classification={**CLS, "result": "continuing_objective", "horizon": "persistent"})
    with pytest.raises(LedgerError, match="ask.prompt_too_long"):
        compile_(ws, staged=stage(ws, prompt=b"/goal " + b"x" * 4000 + b"\n"), capability="native_goal", host=host, classification={**CLS, "result": "continuing_objective", "horizon": "persistent"})
    assert store.verify(ws) == []


def test_non_human_actor_needs_authorization_to_compile_or_confirm(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    agent = {"kind": "agent", "id": "ci", "authority": "preauthorized"}
    with pytest.raises(NeedsInput, match="authorization"):
        compile_(ws, actor=agent)
    (ws.rf_dir / "authorizations").mkdir()
    (ws.rf_dir / "authorizations" / "ci.json").write_text(json.dumps({"schema": "ringframe.authorization/1", "actor": "agent:ci", "granted_by": "human:owner", "time": "t",
        "allowed": {"capabilities": ["native_plan"], "effects": ["read"], "dispositions": [], "eval_verdicts": [], "subject_kinds": []}, "expires": "2999-01-01T00:00:00Z"}))
    out = compile_(ws, actor=agent)
    ask.confirm(ws, out["ask_id"], actor=agent)
    assert store.events(ws)[0]["actor"] == {"kind": "agent", "id": "ci", "authority": "preauthorized:authorizations/ci.json"}
    with pytest.raises(NeedsInput):
        compile_(ws, staged=stage(ws), actor=agent, capability="native_direct", classification={**CLS, "task": ["question"], "result": "answer", "effects": ["read"]})


def test_confirmation_surface_comes_from_the_profile_or_is_unknown(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    # unknown host profile: the CLI must not invent a Claude Code surface for a Codex session
    out = compile_(ws, host={"name": "codex", "surface": "native-tui"}, capability="human_handoff")
    rec = ask.confirm(ws, out["ask_id"])
    assert rec["confirmation"]["surface"] is None
    sessions.capture(ws, "codex", {"session_id": "cx", "prompt": "$rf:ask fix the login bug"}, host_version="codex-cli 0.153.4")
    out2 = compile_(ws, staged=stage(ws, prompt=b"/plan Fix.\n"), title="second", host={"name": "codex", "surface": "native-tui"}, capability="native_plan",
                    classification={**CLS, "task": ["implement"], "result": "workspace_change", "effects": ["write"]})
    assert ask.confirm(ws, out2["ask_id"])["confirmation"]["surface"] == "request_user_input"


def _codex_plan(ws, title, prompt):
    # each Ask comes from its own hook-identified Codex session (the hook, not the model, knows the session)
    sessions.capture(ws, "codex", {"session_id": f"s-{title}", "prompt": "$rf:ask fix the login bug"}, host_version="codex-cli 0.153.4")
    return compile_(ws, staged=stage(ws, prompt=prompt), title=title, host={"name": "codex", "version": "codex-cli 0.153.4", "surface": "native-tui", "session_ref": f"s-{title}"}, capability="native_plan",
                    classification={**CLS, "task": ["implement"], "result": "workspace_change", "effects": ["write"]})


def test_submission_matches_when_the_host_strips_its_slash_command_prefix(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    out = _codex_plan(ws, "one", b"/plan Fix the login bug.\n")
    # Codex hands the UserPromptSubmit hook the text after "/plan ", without the file's trailing newline
    rec = sessions.capture(ws, "codex", {"session_id": "s-one", "prompt": "Fix the login bug."})
    sub = ask.submission_from_capture(ws, "codex", "s-one", rec["sha256"])
    assert sub["ask_id"] == out["ask_id"] and sub["match"] == "host_prefix_stripped"
    assert ask.show(ws, ask_id=out["ask_id"])["submission"] == "observed"


def test_ambiguous_submission_prefers_the_delivered_ask_and_otherwise_records_nothing(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    first = _codex_plan(ws, "one", b"/plan Fix the login bug.\n")
    second = _codex_plan(ws, "two", b"/plan Fix the login bug.\n")
    ask.confirm(ws, second["ask_id"])
    ask.delivery_handoff(ws, second["ask_id"])
    rec = sessions.capture(ws, "codex", {"session_id": "s-two", "prompt": "Fix the login bug."})
    sub = ask.submission_from_capture(ws, "codex", "s-two", rec["sha256"])
    assert sub["ask_id"] == second["ask_id"]  # the Ask that was handed off is the one a paste is expected for
    third = _codex_plan(ws, "three", b"/plan Fix the login bug.\n")
    ask.confirm(ws, first["ask_id"]); ask.delivery_handoff(ws, first["ask_id"])
    ask.confirm(ws, third["ask_id"]); ask.delivery_handoff(ws, third["ask_id"])
    rec2 = sessions.capture(ws, "codex", {"session_id": "s-three", "prompt": "Fix the login bug."})
    assert ask.submission_from_capture(ws, "codex", "s-three", rec2["sha256"]) is None  # two delivered candidates: no attribution
    assert store.verify(ws) == []


def test_compile_renders_prompt_from_body_and_records_compiler_provenance(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ws = workspace.resolve(cwd=repo).ensure()
    sessions.capture(ws, "codex", {"session_id": "cg", "prompt": "$rf:ask keep checkout fast"}, host_version="codex-cli 0.153.4")
    d = ws.rf_dir / "tmp" / "stage-body"
    d.mkdir(parents=True)
    (d / "source.txt").write_bytes(b"keep checkout fast\n")
    (d / "body.txt").write_bytes(b"Run plans/checkout-perf, every item in order.\n")
    cls = {"task": ["implement"], "result": "continuing_objective", "interaction": "approval_gated", "horizon": "persistent", "effects": ["write"], "concerns": ["performance"]}
    out = compile_(ws, staged=d, title="Checkout goal", capability="native_goal", host={"name": "codex", "surface": "native-tui"}, classification=cls)
    text = ask.prompt_text(ws, out["ask_id"])
    assert text.startswith("/goal Run plans/checkout-perf, every item in order.\n")  # host prefix + body, the CLI added the prefix
    assert "\nRules:\n" in text and "- Knuth: Do not optimize on suspicion; measure first" in text  # labelled directive, selected by the performance concern
    ev = [e for e in store.events(ws) if e["type"] == "ask.compiled"][-1]
    comp = ev["data"]["compiler"]
    assert comp["source"] == "body" and comp["host"]["deltas"] == [] and "practice.knuth" in comp["practice"]["selected"]
    assert comp["practice"]["matched_concerns"] == ["performance"] and len(comp["practice"]["shipped_sha256"]) == 64
    assert store.verify(ws) == []
    with pytest.raises(LedgerError, match="ask.staged_dir"):
        d2 = stage(ws)  # prompt.txt and body.txt together are ambiguous
        (d2 / "body.txt").write_bytes(b"x\n")
        compile_(ws, staged=d2)


def test_compile_rejects_unknown_concern_before_writing(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ws = workspace.resolve(cwd=repo).ensure()
    with pytest.raises(LedgerError, match="ask.classification"):
        compile_(ws, classification={**CLS, "concerns": ["telepathy"]})
    assert not (ws.rf_dir / "asks").exists() or not any((ws.rf_dir / "asks").iterdir())


def test_compile_composed_prompt_records_the_cli_selection_not_the_models_claim(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ws = workspace.resolve(cwd=repo).ensure()
    sessions.capture(ws, "codex", {"session_id": "cc", "prompt": "$rf:ask add the health endpoint"}, host_version="codex-cli 0.153.4")
    d = ws.rf_dir / "tmp" / "stage-composed"
    d.mkdir(parents=True)
    (d / "source.txt").write_bytes(b"add the health endpoint\n")
    (d / "composed.txt").write_bytes(b"Add GET /health returning uptime. Reuse the existing bearer check.\n\nRules:\n- Hyrum: keep every current endpoint's behaviour unchanged.\n- KISS, YAGNI: return only uptime; no options.\n")
    cls = {"task": ["implement"], "result": "workspace_change", "interaction": "approval_gated", "horizon": "session", "effects": ["write"], "concerns": ["api_surface"]}
    out = compile_(ws, staged=d, title="Health", capability="native_plan", host={"name": "codex", "surface": "native-tui"}, classification=cls)
    text = ask.prompt_text(ws, out["ask_id"])
    assert text.startswith("/plan Add GET /health returning uptime. Reuse the existing bearer check.\n") and text.rstrip("\n").endswith("no options.")  # prefix added, nothing appended
    comp = [e for e in store.events(ws) if e["type"] == "ask.compiled"][-1]["data"]["compiler"]
    assert comp["source"] == "composed" and "practice.hyrum" in comp["practice"]["selected"] and "practice.kiss" in comp["practice"]["selected"]
    assert comp["practice"]["matched_concerns"] == ["api_surface"] and comp["host"]["deltas"] == []


def _composed_stage(ws, rules: str):
    d = ws.rf_dir / "tmp" / f"stage-{ids.new_id('x')[-6:]}"
    d.mkdir(parents=True)
    (d / "source.txt").write_bytes(b"add the health endpoint\n")
    (d / "composed.txt").write_bytes(("Add GET /health/details returning uptime and version behind the existing bearer check.\n\nRules:\n" + rules).encode())
    return d


def test_composed_rules_are_audited_against_the_supplied_directives(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ws = workspace.resolve(cwd=repo).ensure()
    cls = {"task": ["implement"], "result": "workspace_change", "interaction": "approval_gated", "horizon": "session", "effects": ["write"], "concerns": ["api_surface"]}
    host = {"name": "codex", "version": "codex-cli 0.153.4", "surface": "native-tui", "session_ref": "cx"}
    good = _composed_stage(ws, "- KISS, YAGNI: Expose only uptime and version; no new options or abstractions.\n- Hyrum: Keep every existing endpoint's observable behaviour unchanged.\n")
    out = compile_(ws, staged=good, title="Health", capability="native_plan", host=host, classification=cls)
    comp = [e for e in store.events(ws) if e["type"] == "ask.compiled"][-1]["data"]["compiler"]
    assert comp["source"] == "composed"
    assert set(comp["applied"]) == {"practice.kiss", "practice.yagni", "practice.hyrum"}
    assert set(comp["omitted"]) == set(comp["practice"]["selected"]) - set(comp["applied"]) and "practice.testing_pyramid" in comp["omitted"]
    assert ask.prompt_text(ws, out["ask_id"]).startswith("/plan Add GET")
    bad = _composed_stage(ws, "- KISS: Keep it small.\n- Telepathy: Read the user's mind.\n")
    with pytest.raises(LedgerError, match="ask.composed_rules"):
        compile_(ws, staged=bad, title="Health", capability="native_plan", host=host, classification=cls)
    norules = ws.rf_dir / "tmp" / "stage-norules"
    norules.mkdir()
    (norules / "source.txt").write_bytes(b"add the health endpoint\n")
    (norules / "composed.txt").write_bytes(b"Add GET /health/details.\n")
    with pytest.raises(LedgerError, match="ask.composed_rules"):
        compile_(ws, staged=norules, title="Health", capability="native_plan", host=host, classification=cls)


def test_ask_list_enumerates_every_compiled_ask_oldest_first(repo):
    ws = workspace.resolve(cwd=repo).ensure()
    assert ask.list_asks(ws) == []
    a = compile_(ws)
    b = compile_(ws, staged=stage(ws, prompt=b"Other.\n"), title="Other")
    ask.confirm(ws, b["ask_id"])
    listed = ask.list_asks(ws)
    assert [x["ask_id"] for x in listed] == [a["ask_id"], b["ask_id"]]
    assert listed[0]["outcome"] == "compiled" and listed[1]["outcome"] == "confirmed" and listed[1]["title"] == "Other"


def test_compile_records_base_commit_and_asks_are_open_until_sealed_or_cancelled(repo):
    import subprocess
    ws = workspace.resolve(cwd=repo).ensure()
    head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    a = compile_(ws)
    b = compile_(ws, title="Second")
    ev = store.events(ws)[0]
    assert ev["data"]["base_commit"] == head
    assert [x["state"] for x in ask.list_asks(ws)] == ["open", "open"]
    assert [x["ask_id"] for x in ask.open_asks(ws)] == [a["ask_id"], b["ask_id"]]
    ask.cancel(ws, b["ask_id"])
    assert [x["state"] for x in ask.list_asks(ws)] == ["open", "cancelled"]
    assert [x["ask_id"] for x in ask.open_asks(ws)] == [a["ask_id"]]
    # a seal event naming the Ask in its basis closes it
    store.append(ws, {"schema": store.SCHEMA, "event_id": ids.new_id("evt"), "type": "seal.created", "time": sessions.now(), "id": "sel_x",
                      "actor": {"kind": "human", "id": "local-user"}, "links": [], "data": {
                          "basis": {"asks": [a["ask_id"]]}, "eval": None, "subject": {"kind": "git_commit", "ref": head}, "disposition": "accepted",
                          "authority": {"kind": "human", "id": "local-user", "authority": "interactive"},
                          "artifact": {"role": "seal_receipt", "path": "seals/sel_x.json", "bytes": 0, "sha256": "0" * 64}}})
    assert [x["state"] for x in ask.list_asks(ws)] == ["sealed", "cancelled"] and ask.open_asks(ws) == []


def test_compile_outside_git_records_no_base_commit(tmp_path):
    ws = workspace.resolve(explicit=tmp_path).ensure()
    compile_(ws)
    assert store.events(ws)[0]["data"]["base_commit"] is None
