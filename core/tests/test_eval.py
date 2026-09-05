import json
import subprocess

import pytest

from ringframe import evaluate, store, workspace
from ringframe.store import LedgerError


def ws_for(repo):
    return workspace.resolve(cwd=repo).ensure()


def head(repo):
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def definition(**kw):
    d = {"schema": "ringframe.eval-definition/1",
         "requirements": [
             {"id": "R1", "text": "README exists", "required": True,
              "evidence": [{"kind": "command", "run": ["test", "-f", "README.md"], "pass_when": {"exit_code": 0}}]},
             {"id": "R2", "text": "human agrees", "required": True, "evidence": [{"kind": "attributed", "source": "human:local-user"}]}],
         "forbidden_effects": [
             {"id": "F1", "text": "no secrets file", "evidence": [{"kind": "command", "run": ["test", "!", "-e", "secrets.txt"], "pass_when": {"exit_code": 0}}]}],
         "freshness": {"max_age": "PT24H"}}
    d.update(kw)
    return d


def test_subject_digests(repo):
    ws = ws_for(repo)
    commit = evaluate.subject_digest(ws, "git_commit", head(repo))
    assert len(commit) == 40
    before = evaluate.subject_digest(ws, "worktree", str(repo))
    (repo / "new.txt").write_text("x")
    assert evaluate.subject_digest(ws, "worktree", str(repo)) != before
    (repo / ".fab7/rf/asks").mkdir(parents=True, exist_ok=True)
    (repo / ".gitignore").write_text("ignored.txt\n")
    (repo / "ignored.txt").write_text("y")
    with_ignore = evaluate.subject_digest(ws, "worktree", str(repo))
    (repo / "ignored.txt").write_text("z")
    assert evaluate.subject_digest(ws, "worktree", str(repo)) == with_ignore  # ignored files do not count
    assert evaluate.subject_digest(ws, "file_set", "README.md,new.txt") != evaluate.subject_digest(ws, "file_set", "README.md")
    assert evaluate.subject_digest(ws, "artifact", str(repo / "README.md")) == store.digest.sha256_file(repo / "README.md")
    with pytest.raises(LedgerError, match="subject.kind"):
        evaluate.subject_digest(ws, "planet", "mars")


def test_freeze_then_run_aligned(repo):
    ws = ws_for(repo)
    frozen = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=definition(), ask_id=None)
    assert frozen["eval_id"].startswith("evl_") and (ws.rf_dir / frozen["definition"]["path"]).exists()
    rec = evaluate.run(ws, frozen["eval_id"], observations=[{"requirement": "R2", "source": "human:local-user", "scope": "all", "time": "t", "statement": "ok", "outcome": "pass", "limitations": []}])
    assert rec["verdict"] == "aligned"
    assert {r["id"]: r["status"] for r in rec["requirements"]} == {"R1": "covered-pass", "R2": "covered-pass"}
    assert rec["forbidden_effects"][0]["status"] == "covered-pass"
    assert rec["subject"]["sha256_before"] == rec["subject"]["sha256_after"]
    ev = store.events(ws)[-1]
    assert ev["type"] == "eval.completed" and ev["data"]["verdict"] == "aligned" and ev["data"]["counts"]["covered_pass"] == 2
    assert ev["links"] == [] and store.verify(ws) == []
    assert (ws.rf_dir / f"evals/{frozen['eval_id']}.json").exists()


def test_run_links_to_ask_and_uncovered_is_incomplete(repo):
    ws = ws_for(repo)
    frozen = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=definition(), ask_id="ask_X")
    rec = evaluate.run(ws, frozen["eval_id"], observations=[])
    assert rec["verdict"] == "incomplete"
    assert rec["requirements"][1]["status"] == "uncovered"
    assert store.events(ws)[-1]["links"] == [{"rel": "evaluates", "id": "ask_X"}]


def test_failed_command_is_drifted_and_indeterminate_on_launch_error(repo):
    ws = ws_for(repo)
    d = definition()
    d["requirements"][0]["evidence"][0]["run"] = ["test", "-f", "missing.md"]
    d["requirements"].append({"id": "R3", "text": "tool missing", "required": False,
                              "evidence": [{"kind": "command", "run": ["no-such-binary-xyz"], "pass_when": {"exit_code": 0}}]})
    frozen = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=d)
    rec = evaluate.run(ws, frozen["eval_id"], observations=[{"requirement": "R2", "source": "human:local-user", "scope": "s", "time": "t", "statement": "ok", "outcome": "pass", "limitations": []}])
    statuses = {r["id"]: r["status"] for r in rec["requirements"]}
    assert statuses == {"R1": "covered-fail", "R2": "covered-pass", "R3": "indeterminate"} and rec["verdict"] == "drifted"


def test_forbidden_effect_observed_is_drifted(repo):
    ws = ws_for(repo)
    (repo / "secrets.txt").write_text("x")
    frozen = evaluate.freeze(ws, subject_kind="worktree", subject_ref=str(repo), definition=definition())
    rec = evaluate.run(ws, frozen["eval_id"], observations=[{"requirement": "R2", "source": "human:local-user", "scope": "s", "time": "t", "statement": "ok", "outcome": "pass", "limitations": []}])
    assert rec["verdict"] == "drifted" and store.events(ws)[-1]["data"]["forbidden_effects_observed"] == ["F1"]


def test_subject_change_during_run_is_incomplete(repo):
    ws = ws_for(repo)
    d = definition()
    d["requirements"][0]["evidence"][0]["run"] = ["sh", "-c", "echo mutated >> README.md"]
    frozen = evaluate.freeze(ws, subject_kind="worktree", subject_ref=str(repo), definition=d)
    rec = evaluate.run(ws, frozen["eval_id"], observations=[{"requirement": "R2", "source": "human:local-user", "scope": "s", "time": "t", "statement": "ok", "outcome": "pass", "limitations": []}])
    assert rec["verdict"] == "incomplete" and "subject.changed" in rec["limitations"]


def test_run_refuses_changed_definition_and_double_run(repo):
    ws = ws_for(repo)
    frozen = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=definition())
    path = ws.rf_dir / frozen["definition"]["path"]
    import os
    os.chmod(path, 0o600)
    path.write_text(path.read_text().replace("README exists", "README missing"))
    with pytest.raises(LedgerError, match="eval.definition_changed"):
        evaluate.run(ws, frozen["eval_id"], definition_sha256=frozen["definition"]["sha256"])
    path.write_text(path.read_text() + " ")  # non-canonical bytes are caught even without the digest
    with pytest.raises(LedgerError, match="eval.definition_changed"):
        evaluate.run(ws, frozen["eval_id"])
    frozen2 = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=definition())
    evaluate.run(ws, frozen2["eval_id"])
    with pytest.raises(LedgerError, match="ledger.immutable"):
        evaluate.run(ws, frozen2["eval_id"])


def test_definition_validation_and_duration():
    with pytest.raises(LedgerError, match="eval.definition"):
        evaluate.validate_definition({"schema": "ringframe.eval-definition/1", "requirements": [{"id": "R1"}]})
    assert evaluate.parse_iso_duration("PT24H") == 86400 and evaluate.parse_iso_duration("P7D") == 7 * 86400
    assert evaluate.parse_iso_duration("P1DT2H30M") == 86400 + 9000
