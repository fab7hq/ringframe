"""Conversation output contracts, separate from the complete observation views."""

import hashlib
import json

import pytest

from ringframe import cli, store, workspace
from tests.test_cli import CLS, ROUTE, host, run, staged


ACTION_ARGS = [
    ["init"], ["sync"],
    ["ask", "compile", "--staged", "stage", "--title", "T", "--capability", "native_plan",
     "--classification", CLS, "--route", ROUTE, "--host", host()],
    ["ask", "copy", "--ask", "a"], ["ask", "confirm", "--ask", "a"],
    ["ask", "cancel", "--ask", "a"], ["ask", "submitted", "--ask", "a"],
    ["ask", "delivery", "--ask", "a", "--handoff"],
    ["eval", "open"],
    ["eval", "close", "--eval", "e", "--intent", "{}", "--judgement", "{}"],
    ["seal", "create", "--disposition", "accepted"],
    ["sessions", "capture", "--host", "codex"],
    ["sessions", "prune", "--older-than", "7d"],
    ["export", "--ask", "a", "--out", "out.tar"],
]


FETCH_ARGS = [
    ["profile", "show", "--host", "codex"],
    ["deltas", "domains"], ["deltas", "list"],
    ["deltas", "render", "--host", "codex", "--capability", "native_plan", "--classification", CLS],
    ["ask", "list"], ["ask", "show"], ["ask", "resolve"], ["eval", "list"],
    ["seal", "check", "--seal", "sel_missing"], ["ledger", "verify"],
]


@pytest.mark.parametrize("args", FETCH_ARGS)
@pytest.mark.parametrize("flag", ["--json", "--minimal"])
def test_fetch_flags_work_before_between_and_after_subcommands(repo, monkeypatch, args, flag):
    outputs = [run(repo, *argv, monkeypatch=monkeypatch) for argv in
               ([flag, *args], [args[0], flag, *args[1:]], [*args, flag])]
    assert outputs[0] == outputs[1] == outputs[2]
    assert outputs[0][0] in (0, 2, 3)
    assert not (repo / ".fab7").exists()


@pytest.mark.parametrize("args", ACTION_ARGS)
@pytest.mark.parametrize("flag", ["--json", "--minimal"])
@pytest.mark.parametrize("before", [True, False])
def test_action_rejects_output_flags_before_dispatch(repo, monkeypatch, args, flag, before):
    monkeypatch.setattr(cli, "_dispatch", lambda *a: pytest.fail("invalid flags reached an action"))
    argv = [flag, *args] if before else [*args, flag]
    with pytest.raises(SystemExit) as exc:
        run(repo, *argv, monkeypatch=monkeypatch)
    assert exc.value.code == 1
    assert not (repo / ".fab7").exists()


def compile_ask(repo, monkeypatch, name="a"):
    code, result, _ = run(repo, "ask", "compile", "--staged", staged(repo, name),
                          "--title", name, "--capability", "native_plan",
                          "--classification", CLS, "--route", ROUTE, "--host", host(name),
                          monkeypatch=monkeypatch)
    assert code == 0
    return result


def test_action_default_is_concise_but_keeps_full_record(repo, monkeypatch):
    result = compile_ask(repo, monkeypatch)
    assert set(result) == {"ask_id", "prompt_path", "delivery_mode", "source_verified"}
    ws = workspace.resolve(cwd=repo)
    event = store.events(ws)[0]
    assert {"source", "prompt", "compiler", "route_explanation", "host"} <= event["data"].keys()
    code, copied, _ = run(repo, "ask", "copy", "--ask", result["ask_id"], monkeypatch=monkeypatch)
    assert code == 0 and copied == "Fix login.\n"
    code, cancelled, _ = run(repo, "ask", "cancel", "--ask", result["ask_id"], monkeypatch=monkeypatch)
    assert code == 0 and cancelled == {"ask_id": result["ask_id"], "state": "cancelled"}
    assert store.verify(ws) == []


def test_action_json_is_compact_and_copy_preserves_exact_bytes(repo, monkeypatch):
    import sys
    stage = staged(repo)
    from pathlib import Path
    Path(stage, "prompt.txt").write_bytes(b'{"task":"Fix login"}')
    # A JSON-looking prompt must not be wrapped, parsed or given a newline.
    result = run(repo, "ask", "compile", "--staged", stage, "--title", "T",
                 "--capability", "native_plan", "--classification", CLS,
                 "--route", ROUTE, "--host", host(), monkeypatch=monkeypatch)[1]
    raw = sys.stdout.getvalue()
    assert raw == json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    assert cli.main(["--workspace", str(repo), "ask", "copy", "--ask", result["ask_id"]]) == 0
    assert sys.stdout.getvalue()[len(raw):] == '{"task":"Fix login"}'


def test_seal_action_returns_report_facts_and_persisted_receipt(repo, monkeypatch):
    from pathlib import Path
    result = compile_ask(repo, monkeypatch)
    code, sealed, _ = run(repo, "seal", "create", "--disposition", "accepted", monkeypatch=monkeypatch)
    assert code == 0
    assert sealed["asks"] == [{"ask_id": result["ask_id"], "title": "a"}]
    assert sealed["eval"] is None and sealed["limitations"]
    receipt = json.loads(Path(sealed["receipt_path"]).read_bytes())
    assert receipt["seal_id"] == sealed["seal_id"] and receipt["limitations"] == sealed["limitations"]
    assert {"schema", "authority", "subject", "time"} <= receipt.keys()


def test_resolve_and_chooser_project_candidates_without_changing_full_view(repo, monkeypatch):
    asks = [compile_ask(repo, monkeypatch, name) for name in ("a", "b")]
    for command in ("resolve", "show"):
        code, full, _ = run(repo, "ask", command, "--json", monkeypatch=monkeypatch)
        small_code, small, _ = run(repo, "ask", command, "--minimal", monkeypatch=monkeypatch)
        assert code == small_code == (0 if command == "resolve" else 3)
        assert {c["ask_id"] for c in small["candidates"]} == {a["ask_id"] for a in asks}
        assert all(set(c) == {"ask_id", "title", "state", "capability"} for c in small["candidates"])
        assert all({"source", "prompt", "base_commit", "session_ref"} <= c.keys() for c in full["candidates"])


@pytest.mark.parametrize("effective", [False, True])
def test_delta_list_minimal_keeps_directives_not_selection_metadata(repo, monkeypatch, effective):
    args = ["deltas", "list", *(["--effective"] if effective else [])]
    _, full, _ = run(repo, *args, "--json", monkeypatch=monkeypatch)
    code, small, _ = run(repo, *args, "--minimal", monkeypatch=monkeypatch)
    assert code == 0
    entries = small.values() if effective else small["practice"]
    assert all(set(e) <= {"id", "label", "text"} and e["id"] and e["text"] for e in entries)
    assert len(json.dumps(small)) < len(json.dumps(full))


def test_eval_action_retains_digest_needed_by_judges(repo, monkeypatch):
    result = compile_ask(repo, monkeypatch)
    run(repo, "ask", "confirm", "--ask", result["ask_id"], monkeypatch=monkeypatch)
    code, opened, _ = run(repo, "eval", "open", monkeypatch=monkeypatch)
    assert code == 0
    from pathlib import Path
    assert opened["brief"]["sha256"] == hashlib.sha256(Path(opened["brief_path"]).read_bytes()).hexdigest()
    assert set(opened) == {"eval_id", "brief_path", "brief", "changes", "anchor", "subject"}


def test_minimal_failure_keeps_verification_reason(repo, monkeypatch):
    code, out, _ = run(repo, "seal", "check", "--seal", "sel_missing", "--minimal", monkeypatch=monkeypatch)
    assert code == 2 and out["codes"] == ["seal.receipt_missing"]


def test_profile_minimal_omits_null_activation_and_preserves_actionable_fields(repo, monkeypatch):
    _, full, _ = run(repo, "profile", "show", "--host", "codex", "--json", monkeypatch=monkeypatch)
    code, small, _ = run(repo, "profile", "show", "--host", "codex", "--minimal", monkeypatch=monkeypatch)
    assert code == 0
    assert small["routing"] == full["routing"]
    for cap, source in zip(small["capabilities"], full["capabilities"]):
        assert cap["selection"] == source["selection"]
        assert cap["confirmation"]["tool"] == source["confirmation"]["tool"]
        assert not any(v is None for v in cap.get("activation", {}).values())
        assert not cap.get("activation") == {}
