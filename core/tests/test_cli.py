import io
import json
import os
import subprocess
import sys

import pytest

from ringframe import __version__, cli
from tests.test_eval import commit, head, intent, judgement, two_asks_and_work

CLS = json.dumps({"task": ["plan"], "result": "plan", "interaction": "approval_gated", "horizon": "session", "effects": ["read"]})
ROUTE = json.dumps({"fits": "f", "alternatives": [], "continuation": "c", "effects": "e", "gaps": []})


def run(repo, *args, stdin=None, monkeypatch=None):
    out, err = io.StringIO(), io.StringIO()
    if stdin is not None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    code = cli.main(["--workspace", str(repo), *args])
    text = out.getvalue()
    return code, (json.loads(text) if text.strip().startswith("{") else text), err.getvalue()


def host(session="s1"):
    return json.dumps({"name": "claude-code", "version": "2.1.260", "surface": "native-tui", "session_ref": session})


def staged(repo, name="stage-1"):
    d = repo / ".fab7/rf/tmp" / name
    d.mkdir(parents=True)
    (d / "source.txt").write_bytes(b"fix login\n")
    (d / "prompt.txt").write_bytes(b"Fix login.\n")
    return str(d)


def confirm(repo, mp, **kw):
    cap = kw.get("capability", "native_plan")
    code, out, err = run(repo, "ask", "compile", "--staged", staged(repo, kw.get("stage", "stage-1")), "--title", kw.get("title", "Login"),
                         "--capability", cap, "--classification", CLS, "--route", ROUTE, "--host", host(kw.get("session", "s1")), "--json", monkeypatch=mp)
    if code == 0:
        c2, o2, _ = run(repo, "ask", "confirm", "--ask", out["ask_id"], "--json", monkeypatch=mp)
        assert c2 == 0 and o2["confirmation"]["observed_by"] == "skill"
    return code, out, err


def test_init_and_profile_show(repo, monkeypatch):
    code, out, _ = run(repo, "init", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["rf_dir"].endswith(".fab7/rf") and (repo / ".fab7/rf/.gitignore").exists()
    code, out, _ = run(repo, "profile", "show", "--host", "claude-code", "--version", "2.1.260", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["profile_id"] == "claude-code" and len(out["sha256"]) == 64
    code, out, _ = run(repo, "profile", "show", "--host", "cursor", "--json", monkeypatch=monkeypatch)
    assert out["profile_id"] == "unknown"


def test_ask_confirm_show_delivery_flow(repo, monkeypatch):
    payload = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "s1", "prompt": "/rf:ask fix login", "cwd": str(repo)})
    code, out, _ = run(repo, "sessions", "capture", "--host", "claude-code", "--json", stdin=payload, monkeypatch=monkeypatch)
    assert code == 0 and out["captured"] is True
    code, out, _ = confirm(repo, monkeypatch)
    assert code == 0 and set(out) == {"ask_id", "source", "prompt", "prompt_path", "delivery_mode", "source_verified"} and out["source_verified"] == "exact"
    ask_id = out["ask_id"]
    hook = json.dumps({"hook_event_name": "PostToolUse", "session_id": "s1", "tool_name": "EnterPlanMode", "tool_use_id": "t1", "tool_response": {"ok": 1}})
    code, out, _ = run(repo, "ask", "delivery", "--from-hook", "--json", stdin=hook, monkeypatch=monkeypatch)
    assert code == 0 and out["recorded"] is True and out["state"] == "native_accepted"
    code, out, _ = run(repo, "ask", "delivery", "--from-hook", "--json", stdin=hook, monkeypatch=monkeypatch)
    assert code == 0 and out["recorded"] is False  # never fails the host turn
    code, out, _ = run(repo, "ask", "show", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["ask_id"] == ask_id and out["delivery"] == "native_accepted"
    code, out, _ = run(repo, "ledger", "verify", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out == {"findings": [], "clean": True}


def test_ask_handoff_state_and_resolution_exit_codes(repo, monkeypatch):
    code, a, _ = confirm(repo, monkeypatch)
    code, out, _ = run(repo, "ask", "delivery", "--ask", a["ask_id"], "--handoff", monkeypatch=monkeypatch)
    assert code == 0 and "prompt.txt" in out and "Claude Code TUI" in out
    code, out, err = run(repo, "ask", "delivery", "--ask", a["ask_id"], "--state", "unavailable", "--reason", "x", "--json", monkeypatch=monkeypatch)
    assert code == 2 and out["error"] == "delivery.duplicate"
    code, b, _ = confirm(repo, monkeypatch, stage="stage-2", title="Logout", session="s2", capability="native_direct")
    code, out, _ = run(repo, "ask", "show", "--json", monkeypatch=monkeypatch)
    assert code == 3 and out["needs_input"] == "chooser" and {c["id"] for c in out["candidates"]} == {a["ask_id"], b["ask_id"]}
    code, out, _ = run(repo, "ask", "resolve", "--session", "s2", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["rule_applied"] == "same_session" and out["candidates"][0]["id"] == b["ask_id"]
    code, out, _ = run(repo, "ask", "show", "--ask", "Logout", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["ask_id"] == b["ask_id"]


def test_ask_compile_cancel_submitted_copy_and_usage_errors(repo, monkeypatch):
    code, out, _ = run(repo, "ask", "compile", "--staged", staged(repo), "--title", "t", "--capability", "native_plan", "--classification", CLS,
                       "--route", ROUTE, "--host", host(), "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["delivery_mode"] == "native_dispatch"
    code, c, _ = run(repo, "ask", "cancel", "--ask", out["ask_id"], "--reason", "nah", "--json", monkeypatch=monkeypatch)
    assert code == 0 and c["cancellation"] == {"observed_by": "skill"}
    code, s, _ = run(repo, "ask", "submitted", "--ask", out["ask_id"], "--as-modified", "--json", monkeypatch=monkeypatch)
    assert code == 0 and s["state"] == "attributed" and s["as_modified"] is True
    code, text, _ = run(repo, "ask", "copy", "--ask", out["ask_id"], monkeypatch=monkeypatch)
    assert code == 0 and text == "Fix login.\n"
    code, out, err = run(repo, "ask", "compile", "--staged", "/nope", "--title", "t", "--capability", "native_plan", "--classification", CLS,
                         "--route", ROUTE, "--host", host(), "--json", monkeypatch=monkeypatch)
    assert code == 2 and out["error"] == "ask.staged_dir"
    with pytest.raises(SystemExit) as e:
        run(repo, "ask", "compile", monkeypatch=monkeypatch)
    assert e.value.code == 1
    code, out, _ = run(repo, "ask", "compile", "--staged", staged(repo, "s3"), "--title", "t", "--capability", "native_plan",
                       "--classification", "{not json", "--route", ROUTE, "--host", host(), "--json", monkeypatch=monkeypatch)
    assert code == 1 and out["error"] == "usage"


def test_capture_of_a_pasted_prompt_records_observed_submission(repo, monkeypatch):
    code, out, _ = run(repo, "ask", "compile", "--staged", staged(repo), "--title", "t", "--capability", "native_direct", "--classification", CLS,
                       "--route", ROUTE, "--host", json.dumps({"name": "codex", "surface": "native-tui"}), "--json", monkeypatch=monkeypatch)
    assert code == 0
    payload = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "c9", "prompt": "Fix login.\n", "cwd": str(repo)})
    code, cap, _ = run(repo, "sessions", "capture", "--host", "codex", "--json", stdin=payload, monkeypatch=monkeypatch)
    assert code == 0 and cap["captured"] is True and cap["submission"]["ask_id"] == out["ask_id"] and cap["submission"]["state"] == "observed"
    code, shown, _ = run(repo, "ask", "show", "--json", monkeypatch=monkeypatch)
    assert shown["submission"] == "observed" and shown["outcome"] == "compiled"


def test_eval_and_seal_cli(repo, monkeypatch, tmp_path):
    ws, a, b, sha = two_asks_and_work(repo)
    code, out, _ = run(repo, "eval", "open", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["basis"]["asks"] == [a, b] and out["subject"]["ref"] == sha and out["brief_path"].endswith("brief.json")
    sha_b = out["brief"]["sha256"]
    items = [{"id": "i1", "text": "Expose an uptime endpoint", "ask_id": a, "status": "active"}]
    (tmp_path / "intent.json").write_text(json.dumps(intent(sha_b, items)))
    files = []
    for n, ang in enumerate(("coverage", "drift", "adversary")):
        f = tmp_path / f"j{n}.json"
        f.write_text(json.dumps(judgement(sha_b, ang, {"i1": "yes"}, {"docs/notes.md": "unexplained"})))
        files += ["--judgement", f"@{f}"]
    code, out2, _ = run(repo, "eval", "close", "--eval", out["eval_id"], "--intent", f"@{tmp_path / 'intent.json'}", *files[:4], "--json", monkeypatch=monkeypatch)
    assert code == 2 and out2["error"] == "eval.too_few_judges"
    code, rec, _ = run(repo, "eval", "close", "--eval", out["eval_id"], "--intent", f"@{tmp_path / 'intent.json'}", *files, "--json", monkeypatch=monkeypatch)
    assert code == 0 and rec["verdict"] == "drifted" and rec["confidence"] == 1.0 and rec["drift"]["commission"][0]["path"] == "docs/notes.md"
    code, out3, _ = run(repo, "eval", "close", "--eval", out["eval_id"], "--intent", f"@{tmp_path / 'intent.json'}", *files, "--json", monkeypatch=monkeypatch)
    assert code == 2 and out3["error"] == "ledger.immutable"
    code, listed, _ = run(repo, "eval", "list", "--json", monkeypatch=monkeypatch)
    assert [e["verdict"] for e in listed["evals"]] == ["drifted"]
    code, receipt, _ = run(repo, "seal", "create", "--disposition", "accepted", "--note", "shipping the drift knowingly", "--json", monkeypatch=monkeypatch)
    assert code == 0 and receipt["disposition"] == "accepted" and receipt["eval"]["verdict"] == "drifted" and receipt["note"] == "shipping the drift knowingly"
    code, out, _ = run(repo, "seal", "create", "--disposition", "accepted", "--json", monkeypatch=monkeypatch)
    assert code == 2 and out["error"] == "seal.refused" and out["refusal_codes"] == ["seal.no_open_ask"]
    code, out, _ = run(repo, "eval", "open", "--json", monkeypatch=monkeypatch)
    assert code == 2 and out["error"] == "eval.no_open_ask"
    code, out, _ = run(repo, "seal", "check", "--seal", receipt["seal_id"], "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["fresh"] is True and out["subject_matches"] is True
    commit(repo, {"README.md": "changed\n"}, "change")
    code, out, _ = run(repo, "seal", "check", "--seal", receipt["seal_id"], "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["fresh"] is True and out["subject_matches"] is False  # a fact, not a refusal
    code, out, _ = run(repo, "seal", "check", "--seal", "sel_nope", "--json", monkeypatch=monkeypatch)
    assert code == 2 and out["fresh"] is False
    with pytest.raises(SystemExit) as e:
        run(repo, "seal", "create", "--disposition", "shipped", "--json", monkeypatch=monkeypatch)
    assert e.value.code == 1


def test_export_and_prune(repo, monkeypatch, tmp_path):
    code, a, _ = confirm(repo, monkeypatch)
    code, out, _ = run(repo, "export", "--ask", a["ask_id"], "--out", str(tmp_path / "x.tar"), "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["files"] == 3
    import tarfile
    names = tarfile.open(tmp_path / "x.tar").getnames()
    assert any(n.endswith("prompt.txt") for n in names) and any(n.endswith("ledger.jsonl") for n in names)
    code, out, _ = run(repo, "sessions", "prune", "--older-than", "7d", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["removed"] == []


def test_module_entrypoint_and_version():
    cp = subprocess.run([sys.executable, "-m", "ringframe", "--version"], capture_output=True, text=True,
                        env={**os.environ, "PYTHONPATH": "core"})
    assert cp.returncode == 0 and cp.stdout.strip() == f"ringframe {__version__}"


def test_deltas_commands(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    code, out, _ = run(repo, "deltas", "list", "--host", "codex", "--capability", "native_goal", "--json", monkeypatch=monkeypatch)
    assert code == 0 and [e["id"] for e in out["host"]] == ["codex.native_goal.item_loop", "codex.native_goal.terminal_condition"]
    assert all(e["status"] == "candidate" for e in out["host"])
    code, out, _ = run(repo, "deltas", "list", "--effective", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["practice.kiss"]["layer"] == "user"
    cls = json.dumps({"task": ["implement"], "result": "workspace_change", "interaction": "approval_gated", "horizon": "session", "effects": ["write"], "concerns": ["api_surface"]})
    code, out, _ = run(repo, "deltas", "render", "--host", "codex", "--host-version", "codex-cli 0.153.4", "--capability", "native_plan", "--classification", cls, "--json", monkeypatch=monkeypatch)
    assert code == 0 and "practice.hyrum" in out["practice"]["selected"] and out["text"]
    code, text, _ = run(repo, "deltas", "render", "--host", "codex", "--host-version", "codex-cli 0.153.4", "--capability", "native_plan", "--classification", cls, monkeypatch=monkeypatch)
    assert code == 0 and "observable behaviour" in text


def test_deltas_render_json_exposes_each_directive_for_composition(repo, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    cls = json.dumps({"task": ["implement"], "result": "workspace_change", "interaction": "approval_gated", "horizon": "session", "effects": ["write"], "concerns": ["api_surface"]})
    code, out, _ = run(repo, "deltas", "render", "--host", "codex", "--host-version", "codex-cli 0.153.4", "--capability", "native_plan", "--classification", cls, "--json", monkeypatch=monkeypatch)
    assert code == 0
    ids = [e["id"] for e in out["practice"]["entries"]]
    assert ids == out["practice"]["selected"] and all(e["text"] for e in out["practice"]["entries"])
    assert out["host"]["entries"] == []  # nothing qualified yet


def test_eval_list_cli(repo, monkeypatch):
    code, out, _ = run(repo, "eval", "list", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out == {"evals": []}


def test_ask_list_cli(repo, monkeypatch):
    code, out, _ = run(repo, "ask", "list", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out == {"asks": []}


@pytest.mark.parametrize("host_name", ["codex", "claude-code"])
def test_hook_uses_payload_project_and_initializes_private_storage(repo, monkeypatch, host_name):
    project = repo / "test"
    project.mkdir()
    monkeypatch.chdir(repo)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"cwd": str(project), "session_id": "nested", "prompt": "/rf:ask fix login"})))
    assert cli.main(["sessions", "capture", "--host", host_name, "--json"]) == 0
    rf = project / ".fab7/rf"
    assert (rf / f"sessions/{host_name}/nested/prompts.jsonl").exists()
    assert (rf / ".gitignore").read_text() == "*\n"
    assert rf.stat().st_mode & 0o777 == 0o700
    assert not (repo / ".fab7").exists()


def test_global_init_materializes_deltas_and_preserves_customizations(repo, tmp_path, monkeypatch):
    from importlib.resources import files
    home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(home))
    code, out, _ = run(repo, "init", "--global", "--json", monkeypatch=monkeypatch)
    assert code == 0
    root = home / ".fab7/rt"
    assert not (repo / ".fab7").exists()
    for rel in ["deltas/codex.yaml", "deltas/claude-code.yaml", "deltas/practice/software-development.yaml"]:
        assert (root / rel).read_bytes() == (files("ringframe") / rel).read_bytes()
    catalog = root / "deltas/codex.yaml"
    catalog.write_text(catalog.read_text() + "\n# User customization preserved\n")
    before = catalog.read_bytes()
    code, _, _ = run(repo, "init", "--global", "--json", monkeypatch=monkeypatch)
    assert code == 0 and catalog.read_bytes() == before
    assert set(root.iterdir()) == {root / "deltas"}


def test_nested_compile_and_hook_delivery_keep_records_in_project(repo, monkeypatch):
    project = repo / "test"
    project.mkdir()
    monkeypatch.chdir(project)
    # No explicit workspace: reproduce a CLI invoked from a nested host project.
    assert cli.main(["ask", "compile", "--staged", staged(project), "--title", "Login", "--capability", "native_plan", "--classification", CLS, "--route", ROUTE, "--host", host(), "--json"]) == 0
    from ringframe import ask, store, workspace
    ws = workspace.resolve(cwd=project)
    record = ask.list_asks(ws)[0]
    ask_id = record["ask_id"]
    assert cli.main(["ask", "confirm", "--ask", ask_id, "--json"]) == 0
    monkeypatch.chdir(repo)
    payload = {"hook_event_name": "PostToolUse", "cwd": str(project), "session_id": "s1", "tool_name": "EnterPlanMode", "tool_use_id": "t1", "tool_response": {"ok": 1}}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert cli.main(["ask", "delivery", "--from-hook", "--json"]) == 0
    assert ask.show(ws, ask_id)["delivery"] == "native_accepted"
    assert store.verify(ws) == []
    assert (ws.rf_dir / "asks" / ask_id / "prompt.txt").exists()
    assert not (ws.rf_dir / "tmp/stage-1").exists()
    assert not (repo / ".fab7").exists()


def test_compile_reads_merged_ledger_delta_files(repo, monkeypatch):
    from ringframe import deltas, workspace
    ws = workspace.resolve(cwd=repo).ensure()
    workspace.initialize_user()
    local = ws.rt_dir / "deltas/practice/software-development.yaml"
    local.write_text("concerns: [project_special]\nrender: {core_cap: 1}\nentries: [{id: practice.kiss, text: Use the project setting.}]\n")
    cls = json.dumps({"task": ["implement"], "result": "workspace_change", "interaction": "approval_gated", "horizon": "session", "effects": ["write"], "concerns": ["project_special"]})
    stage = repo / "stage"
    stage.mkdir()
    (stage / "source.txt").write_text("fix login")
    (stage / "body.txt").write_text("Fix login.")
    code, out, _ = run(repo, "ask", "compile", "--staged", str(stage), "--title", "Login", "--capability", "native_plan", "--classification", cls, "--route", ROUTE, "--host", host(), "--json", monkeypatch=monkeypatch)
    assert code == 0
    from pathlib import Path
    assert "Use the project setting." in Path(out["prompt_path"]).read_text()
    code, out, _ = run(repo, "deltas", "list", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["practice"][0]["text"] == "Use the project setting."
    assert deltas.load_practice_catalog()["entries"][0]["text"] != "Use the project setting."


def test_profile_cli_exposes_routing_and_capability_sources(repo, monkeypatch):
    from ringframe import profiles
    for name in ("codex", "claude-code"):
        code, out, _ = run(repo, "profile", "show", "--host", name, "--json", monkeypatch=monkeypatch)
        assert code == 0 and out["routing"] == profiles.load(name)["routing"]
        assert out["routing"]["precedence"]
        assert set(out["routing"]["precedence"]) == {cap["id"] for cap in out["capabilities"]}
        for cap in out["capabilities"]:
            assert cap["selection"] and cap["sources"]
            assert all(url.startswith("https://") for url in cap["sources"])
            assert cap["delivery_mode"] in {"native_dispatch", "human_handoff"}


def test_delta_listing_exposes_merged_concern_vocabulary(repo, monkeypatch):
    from ringframe import workspace
    ws = workspace.resolve(cwd=repo).ensure()
    (ws.rt_dir / "deltas/practice/software-development.yaml").write_text("concerns: [team_boundary]\n")
    code, out, _ = run(repo, "deltas", "list", "--json", monkeypatch=monkeypatch)
    assert code == 0 and out["concerns"] == ["team_boundary"]
