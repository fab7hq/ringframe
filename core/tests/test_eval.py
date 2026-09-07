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
    assert rec["basis"]["submission"] == "unobserved" and "submission of the compiled prompt: unobserved" in rec["limitations"]


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


def test_eval_list_enumerates_records_newest_last(repo):
    ws = ws_for(repo)
    assert evaluate.list_records(ws) == []
    a = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=definition())
    evaluate.run(ws, a["eval_id"], observations=[{"requirement": "R2", "source": "human:local-user", "scope": "s", "time": "2026-01-01T00:00:00Z", "statement": "ok", "outcome": "pass", "limitations": []}])
    b = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=definition())
    listed = evaluate.list_records(ws)
    assert [r["eval_id"] for r in listed] == [a["eval_id"], b["eval_id"]]
    assert listed[0]["verdict"] == "aligned" and listed[0]["subject"]["ref"] == head(repo) and listed[0]["state"] == "completed"
    assert listed[1]["verdict"] is None and listed[1]["state"] == "frozen"  # frozen, not yet run


def commit(repo, files: dict, message="change"):
    for name, text in files.items():
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message], check=True)
    return head(repo)


def obs(req, outcome="pass", statement="Pass"):
    return {"requirement": req, "source": "human:local-user", "scope": "s", "time": "2026-01-01T00:00:00Z", "statement": statement, "outcome": outcome, "limitations": []}


def test_attestation_only_is_attested_not_aligned(repo):
    ws = ws_for(repo)
    d = definition(requirements=[{"id": "R1", "text": "human agrees", "required": True, "evidence": [{"kind": "attributed", "source": "human:local-user"}]}], forbidden_effects=[])
    f = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=d)
    rec = evaluate.run(ws, f["eval_id"], observations=[obs("R1")])
    assert rec["verdict"] == "attested" and rec["evidence_floor"] == "E5" and rec["requirements"][0]["strongest"] == "E5"
    assert any("attested" in l for l in rec["limitations"])


def test_freeze_refuses_attestation_only_when_the_project_declares_tests(repo):
    ws = ws_for(repo)
    commit(repo, {"package.json": json.dumps({"name": "x", "scripts": {"test": "node --test"}})})
    d = definition(requirements=[{"id": "R1", "text": "human agrees", "required": True, "evidence": [{"kind": "attributed", "source": "human:local-user"}]}], forbidden_effects=[])
    with pytest.raises(LedgerError, match="eval.no_command_evidence"):
        evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=d)
    f = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=head(repo), definition=d, attested_only=True)
    frozen = json.loads((ws.rf_dir / f"evals/{f['eval_id']}.definition.json").read_text())
    assert frozen["attested_only"] is True and frozen["scope"]["test_command"] == ["npm", "test"]


def test_agent_written_test_alone_is_indeterminate(repo):
    ws = ws_for(repo)
    sha = commit(repo, {"tests/a.test.sh": "exit 0\n", "src/a.txt": "x\n"})
    d = definition(requirements=[{"id": "R1", "text": "feature", "required": True, "evidence": [{"kind": "command", "run": ["sh", "tests/a.test.sh"], "origin": "agent"}]}], forbidden_effects=[])
    f = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=sha, definition=d)
    rec = evaluate.run(ws, f["eval_id"])
    assert rec["requirements"][0]["status"] == "indeterminate" and rec["verdict"] == "incomplete"
    assert any("written by the change" in l for l in rec["limitations"])
    # with an artifact fact that the test is part of the change, the agent-written test counts
    d2 = definition(requirements=[{"id": "R1", "text": "feature", "required": True, "evidence": [
        {"kind": "command", "run": ["sh", "tests/a.test.sh"], "origin": "agent"}, {"kind": "artifact", "check": "paths_present", "paths": ["tests/a.test.sh", "src/a.txt"]}]}], forbidden_effects=[])
    f2 = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=sha, definition=d2)
    rec2 = evaluate.run(ws, f2["eval_id"])
    assert rec2["requirements"][0]["status"] == "covered-pass" and rec2["evidence_floor"] == "E1" and rec2["verdict"] == "aligned"


def test_artifact_checks_and_drift_from_the_commit(repo):
    ws = ws_for(repo)
    commit(repo, {"package.json": json.dumps({"name": "x", "dependencies": {"a": "1"}}), "src/server.js": "base\n"}, "base")
    sha = commit(repo, {"src/server.js": "base\nfeature\n", "tests/server.test.js": "t\n", "docs/notes.md": "unrelated\n", "package.json": json.dumps({"name": "x", "dependencies": {"a": "1", "b": "2"}})}, "feature")
    d = definition(
        scope={"allowed_paths": ["src/", "tests/"]},
        requirements=[{"id": "R1", "text": "feature implemented", "required": True, "evidence": [{"kind": "artifact", "check": "paths_present", "paths": ["tests/server.test.js"]}]}],
        forbidden_effects=[{"id": "F1", "text": "no new dependency", "evidence": [{"kind": "artifact", "check": "deps_unchanged"}]},
                           {"id": "F2", "text": "no change outside scope", "evidence": [{"kind": "artifact", "check": "scope_clean", "max_unbound_lines": 0}]}])
    f = evaluate.freeze(ws, subject_kind="git_commit", subject_ref=sha, definition=d)
    rec = evaluate.run(ws, f["eval_id"])
    assert rec["verdict"] == "drifted"
    assert {x["id"]: x["status"] for x in rec["forbidden_effects"]} == {"F1": "covered-fail", "F2": "covered-fail"}
    assert rec["drift"]["commission"]["unbound_files"] == ["docs/notes.md", "package.json"] and rec["drift"]["commission"]["unbound_lines"] == 3  # docs (1 line) and package.json (1 removed + 1 added), both outside src/ and tests/
    assert rec["drift"]["omission"] == {"rate": 0.0, "unmet": []} and rec["drift"]["process"] == {}
    assert rec["requirements"][0]["strongest"] == "E2" and rec["evidence_floor"] == "E2"


def test_scaffold_drafts_facts_first(repo):
    ws = ws_for(repo)
    commit(repo, {"package.json": json.dumps({"name": "x", "scripts": {"test": "node --test tests/"}}), "tests/a.test.js": "t\n"}, "base")
    sha = commit(repo, {"src/f.js": "f\n"}, "feature")
    d = evaluate.scaffold(ws, subject_ref=sha, title="Add feature", ask_id=None)
    assert d["schema"] == "ringframe.eval-definition/1" and d["scope"]["test_command"] == ["npm", "test"]
    kinds = [e["kind"] for r in d["requirements"] for e in r["evidence"]]
    assert kinds[0] == "command" and d["requirements"][0]["evidence"][0]["origin"] == "preexisting"
    assert {f["evidence"][0]["check"] for f in d["forbidden_effects"]} == {"deps_unchanged", "scope_clean"}
    assert d["scope"]["allowed_paths"] == ["src/"]  # from the commit's changed paths, for the person to widen or narrow
    evaluate.validate_definition(d)
