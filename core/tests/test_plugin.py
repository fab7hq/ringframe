import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from ringframe import __version__

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "claude"


def test_manifests_are_consistent():
    plugin = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert plugin["name"] == "rf" and plugin["version"] == __version__
    entry, = market["plugins"]
    assert entry["name"] == "rf" and entry["version"] == __version__ and (ROOT / entry["source"]).resolve() == PLUGIN


def test_hooks_reference_executable_scripts():
    hooks = json.loads((PLUGIN / "hooks/hooks.json").read_text())["hooks"]
    assert set(hooks) == {"UserPromptSubmit", "PostToolUse"}
    assert hooks["PostToolUse"][0]["matcher"] == "EnterPlanMode"
    for event in hooks.values():
        for group in event:
            for h in group["hooks"]:
                script = PLUGIN / h["command"].replace('"${CLAUDE_PLUGIN_ROOT}"/', "")
                assert script.exists() and script.stat().st_mode & stat.S_IXUSR


def test_skills_are_explicit_only_and_call_the_cli():
    for name in ("ask", "eval", "seal"):
        text = (PLUGIN / "skills" / name / "SKILL.md").read_text()
        front = text.split("---")[1]
        assert f"name: {name}" in front and "disable-model-invocation: true" in front and "Bash(ringframe *)" in front
        if name == "ask":
            assert "ringframe ask compile" in text and "ringframe ask confirm --ask" in text and "ringframe ask cancel --ask" in text
        assert "NEXT_COMMAND" not in text.split("Never print")[0] or name != "ask"
        assert "ledger.jsonl" not in text  # skills never touch the ledger directly


def _shim(tmp_path):
    """A `ringframe` (and a fake `claude`) on PATH that run this checkout's package."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shim = bin_dir / "ringframe"
    shim.write_text(f'#!/bin/sh\nPYTHONPATH="{ROOT / "core"}" exec "{sys.executable}" -m ringframe "$@"\n')
    shim.chmod(0o755)
    fake_claude = bin_dir / "claude"
    fake_claude.write_text("#!/bin/sh\necho '2.1.263 (Claude Code)'\n")
    fake_claude.chmod(0o755)
    return str(bin_dir)


def _hook(script, payload, cwd, path):
    return subprocess.run([str(PLUGIN / "hooks" / script)], input=payload, cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, "PATH": path})


def test_hooks_exit_zero_without_cli_and_on_garbage(repo, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with_cli = _shim(tmp_path)
    for script in ("capture-prompt.sh", "record-delivery.sh"):
        assert _hook(script, "{}", repo, str(empty)).returncode == 0  # no CLI on PATH
        assert _hook(script, "not json", repo, with_cli).returncode == 0  # malformed stdin
    assert not (repo / ".fab7/rf/ledger.jsonl").exists()


def test_hooks_drive_capture_and_delivery_end_to_end(repo, tmp_path):
    path = _shim(tmp_path) + os.pathsep + os.environ["PATH"]
    submit = json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "sess", "cwd": str(repo), "permission_mode": "default", "prompt": "/rf:ask add a health endpoint"})
    assert _hook("capture-prompt.sh", submit, repo, path).returncode == 0
    captured = json.loads((repo / ".fab7/rf/sessions/claude-code/sess/prompts.jsonl").read_text())
    assert captured["host_version"] == "2.1.263 (Claude Code)"
    stage = repo / ".fab7/rf/tmp/stage-1"
    stage.mkdir(parents=True)
    (stage / "source.txt").write_text("add a health endpoint\n")
    (stage / "prompt.txt").write_text("Add a health endpoint.\n")
    out = subprocess.run(["ringframe", "ask", "compile", "--staged", str(stage), "--title", "Health", "--capability", "native_plan",
                          "--classification", json.dumps({"task": ["implement"], "result": "workspace_change", "interaction": "approval_gated", "horizon": "session", "effects": ["write"]}),
                          "--route", json.dumps({"fits": "f", "alternatives": [], "continuation": "c", "effects": "e", "gaps": []}),
                          "--host", json.dumps({"name": "claude-code", "surface": "native-tui"}), "--json"],
                         cwd=repo, capture_output=True, text=True, env={**os.environ, "PATH": path}, check=True)
    confirmed = json.loads(out.stdout)
    assert confirmed["source_verified"] == "exact"  # session and version resolved from the hook capture
    subprocess.run(["ringframe", "ask", "confirm", "--ask", confirmed["ask_id"], "--json"], cwd=repo, capture_output=True, text=True, env={**os.environ, "PATH": path}, check=True)
    post = json.dumps({"hook_event_name": "PostToolUse", "session_id": "sess", "cwd": str(repo), "tool_name": "EnterPlanMode", "tool_use_id": "toolu_9", "tool_input": {}, "tool_response": {"message": "entered"}})
    assert _hook("record-delivery.sh", post, repo, path).returncode == 0
    shown = json.loads(subprocess.run(["ringframe", "ask", "show", "--json"], cwd=repo, capture_output=True, text=True, env={**os.environ, "PATH": path}, check=True).stdout)
    assert shown["delivery"] == "native_accepted" and shown["ask_id"] == confirmed["ask_id"]
