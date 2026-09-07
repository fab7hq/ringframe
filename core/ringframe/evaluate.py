"""Eval: freeze a definition, digest an exact subject, collect attributed evidence, compute the verdict."""

import json
import re
import subprocess
import time
from pathlib import Path

from ringframe import digest, ids, schema, sessions, store
from ringframe.store import LedgerError
from ringframe.workspace import Workspace

DEFINITION_SCHEMA = "ringframe.eval-definition/1"
KINDS = ("git_commit", "worktree", "file_set", "artifact")
COMMAND_TIMEOUT_S = 600
STDOUT_HEAD = 4096


def parse_iso_duration(text: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", text)
    if not m or not any(m.groups()):
        raise LedgerError("eval.definition", f"freshness.max_age {text!r} is not an ISO 8601 duration like PT24H or P7D")
    d, h, mi = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60


def validate_definition(d: dict) -> None:
    if d.get("schema") != DEFINITION_SCHEMA:
        raise LedgerError("eval.definition", f"schema must be {DEFINITION_SCHEMA}")
    for group in ("requirements", "forbidden_effects"):
        for i, r in enumerate(d.get(group, [])):
            for k in ("id", "text", "evidence"):
                if k not in r:
                    raise LedgerError("eval.definition", f"{group}[{i}].{k} missing")
            for j, e in enumerate(r["evidence"]):
                if e.get("kind") == "command":
                    if not isinstance(e.get("run"), list) or not e["run"]:
                        raise LedgerError("eval.definition", f"{group}[{i}].evidence[{j}].run must be a non-empty list")
                elif e.get("kind") == "attributed":
                    if "source" not in e:
                        raise LedgerError("eval.definition", f"{group}[{i}].evidence[{j}].source missing")
                else:
                    raise LedgerError("eval.definition", f"{group}[{i}].evidence[{j}].kind must be command or attributed")
    parse_iso_duration(d.get("freshness", {}).get("max_age", "PT24H"))


def _git(root, *args) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout


def subject_digest(ws: Workspace, kind: str, ref: str) -> str:
    if kind == "git_commit":
        return _git(ws.root, "rev-parse", f"{ref}^{{tree}}").strip()
    if kind == "worktree":
        root = Path(ref)
        names = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0")
        h = __import__("hashlib").sha256()
        for name in sorted(n for n in names if n):
            p = root / name
            if p.is_file():
                h.update(f"{name}\0{p.stat().st_mode & 0o777:o}\0{digest.sha256_file(p)}\n".encode())
        return h.hexdigest()
    if kind == "file_set":
        h = __import__("hashlib").sha256()
        for pattern in sorted(ref.split(",")):
            for p in sorted(ws.root.glob(pattern.strip())):
                if p.is_file():
                    h.update(f"{p.relative_to(ws.root)}\0{digest.sha256_file(p)}\n".encode())
        return h.hexdigest()
    if kind == "artifact":
        p = Path(ref)
        if not p.is_file():
            raise LedgerError("subject.missing", ref)
        return digest.sha256_file(p)
    raise LedgerError("subject.kind", f"{kind!r} not in {KINDS}")


def freeze(ws: Workspace, *, subject_kind: str, subject_ref: str, definition: dict, ask_id: str | None = None, contract: dict | None = None) -> dict:
    validate_definition(definition)
    if subject_kind not in KINDS:
        raise LedgerError("subject.kind", subject_kind)
    eval_id = ids.new_id("evl")
    frozen = {**definition, "eval_id": eval_id, "subject": {"kind": subject_kind, "ref": subject_ref},
              "basis": {"ask_id": ask_id} if ask_id else {"contract": contract or {}}, "frozen_at": sessions.now()}
    ref = store.publish(ws, f"evals/{eval_id}.definition.json", store.canonical(frozen) + b"\n", role="eval_definition")
    return {"eval_id": eval_id, "definition": ref}


def _run_command(root: Path, spec: dict) -> dict:
    start = time.monotonic()
    out = {"kind": "command", "run": spec["run"], "time": sessions.now()}
    try:
        cp = subprocess.run(spec["run"], cwd=root, capture_output=True, timeout=spec.get("timeout_s", COMMAND_TIMEOUT_S))
        want = spec.get("pass_when", {}).get("exit_code", 0)
        out.update(exit_code=cp.returncode, stdout_sha256=digest.sha256_bytes(cp.stdout), stdout_head=cp.stdout[:STDOUT_HEAD].decode("utf-8", "replace"),
                   stderr_head=cp.stderr[:STDOUT_HEAD].decode("utf-8", "replace"), outcome="pass" if cp.returncode == want else "fail")
    except subprocess.TimeoutExpired:
        out.update(outcome="indeterminate", error="timeout")
    except OSError as e:
        out.update(outcome="indeterminate", error=str(e))
    out["duration_ms"] = int((time.monotonic() - start) * 1000)
    return out


def _status(outcomes: list[str]) -> str:
    if not outcomes:
        return "uncovered"
    if "fail" in outcomes:
        return "covered-fail"
    if all(o == "pass" for o in outcomes):
        return "covered-pass"
    return "indeterminate"


def _evaluate(root: Path, items: list[dict], observations: list[dict]) -> list[dict]:
    results = []
    for item in items:
        evidence = []
        for spec in item["evidence"]:
            if spec["kind"] == "command":
                evidence.append(_run_command(root, spec))
            else:
                for obs in observations:
                    if obs.get("requirement") == item["id"] and obs.get("source") == spec["source"]:
                        evidence.append({"kind": "attributed", **obs})
        results.append({"id": item["id"], "text": item["text"], "required": item.get("required", True),
                        "status": _status([e["outcome"] for e in evidence]), "evidence": evidence})
    return results


def run(ws: Workspace, eval_id: str, observations: list[dict] | None = None, definition_sha256: str | None = None) -> dict:
    def_path = ws.rf_dir / f"evals/{eval_id}.definition.json"
    if not def_path.exists():
        raise LedgerError("eval.missing", eval_id)
    if (ws.rf_dir / f"evals/{eval_id}.json").exists():
        raise LedgerError("ledger.immutable", f"evals/{eval_id}.json")
    raw = def_path.read_bytes()
    definition = json.loads(raw)
    definition_sha = digest.sha256_bytes(raw)
    if (store.canonical(definition) + b"\n" != raw or definition.get("eval_id") != eval_id
            or (definition_sha256 and definition_sha256 != definition_sha)):
        raise LedgerError("eval.definition_changed", eval_id)
    validate_definition(definition)
    subject = definition["subject"]
    before = subject_digest(ws, subject["kind"], subject["ref"])
    root = Path(subject["ref"]) if subject["kind"] == "worktree" else ws.root
    requirements = _evaluate(root, definition.get("requirements", []), observations or [])
    forbidden = _evaluate(root, definition.get("forbidden_effects", []), observations or [])
    after = subject_digest(ws, subject["kind"], subject["ref"])
    limitations = ["attributed observations are not independently verified", "commands are caller-selected"]
    basis = dict(definition["basis"])
    if basis.get("ask_id"):
        from ringframe import ask as _ask  # local import: ask depends on sessions/profiles, not on evaluate
        rec = _ask._by_id(ws).get(basis["ask_id"])
        basis["submission"] = _ask.submission_grade(rec) if rec and rec["compiled"] else "unobserved"
        limitations.append(f"submission of the compiled prompt: {basis['submission']}")
    observed = [f["id"] for f in forbidden if f["status"] == "covered-fail"]
    required = [r for r in requirements if r["required"]]
    if before != after:
        verdict = "incomplete"
        limitations.append("subject.changed")
    elif any(r["status"] == "covered-fail" for r in required) or observed:
        verdict = "drifted"
    elif all(r["status"] == "covered-pass" for r in required) and all(f["status"] == "covered-pass" for f in forbidden):
        verdict = "aligned"
    else:
        verdict = "incomplete"
    record = {"schema": "ringframe.eval/1", "eval_id": eval_id, "basis": basis,
              "definition": {"path": f"evals/{eval_id}.definition.json", "sha256": definition_sha},
              "subject": {**subject, "sha256_before": before, "sha256_after": after},
              "requirements": requirements, "forbidden_effects": forbidden, "verdict": verdict,
              "freshness": definition.get("freshness", {"max_age": "PT24H"}), "limitations": limitations, "time": sessions.now()}
    ref = store.publish(ws, f"evals/{eval_id}.json", store.canonical(record) + b"\n", role="eval_record")
    counts = {k: sum(1 for r in requirements if r["status"] == k.replace("_", "-")) for k in ("covered_pass", "covered_fail", "uncovered", "indeterminate")}
    ask_id = definition["basis"].get("ask_id")
    ev = {"schema": store.SCHEMA, "event_id": ids.new_id("evt"), "type": "eval.completed", "time": record["time"], "id": eval_id,
          "actor": {"kind": "human", "id": "local-user", "authority": "interactive"},
          "links": [{"rel": "evaluates", "id": ask_id}] if ask_id else [],
          "data": {"subject": record["subject"], "definition_sha256": definition_sha, "verdict": verdict, "counts": counts,
                   "forbidden_effects_observed": observed, "artifact": ref,
                   "definition": {"role": "eval_definition", "path": record["definition"]["path"], "bytes": len(raw), "sha256": definition_sha},
                   "limitations": limitations}}
    schema.validate_event(ev)
    store.append(ws, ev)
    return record


def load_record(ws: Workspace, eval_id: str) -> dict | None:
    p = ws.rf_dir / f"evals/{eval_id}.json"
    return json.loads(p.read_bytes()) if p.exists() else None


def list_records(ws: Workspace) -> list[dict]:
    """Every Eval in this workspace, frozen or completed, oldest first: what Seal chooses from."""
    out = []
    d = ws.rf_dir / "evals"
    for defn in sorted(d.glob("*.definition.json")) if d.exists() else []:
        eval_id = defn.name[: -len(".definition.json")]
        frozen = json.loads(defn.read_bytes())
        rec = load_record(ws, eval_id)
        out.append({"eval_id": eval_id, "state": "completed" if rec else "frozen", "frozen_at": frozen.get("frozen_at"),
                    "basis": frozen.get("basis"), "subject": frozen.get("subject"),
                    "verdict": rec.get("verdict") if rec else None, "completed_at": rec.get("time") if rec else None,
                    "path": f"evals/{eval_id}.json" if rec else f"evals/{eval_id}.definition.json"})
    return out
