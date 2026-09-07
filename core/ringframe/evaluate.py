"""Eval: freeze a definition, digest an exact subject, collect layered evidence, compute the verdict and the drift.

Evidence classes, strongest first (ADR-0009): E1 command (with the test's origin), E2 artifact facts the CLI
computes from the subject, E3 trajectory facts from hooks, E4 calibrated judges, E5 the person's verbatim word.
The verdict is computed, never judged; an Eval whose required requirements rest on E5 alone is `attested`,
never `aligned`. Drift is measured from the artifact: commission (changes bound to no requirement), omission
(requirements not met), process (order facts from hooks)."""

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
EVIDENCE_KINDS = ("command", "artifact", "trajectory", "judge", "attributed")
ORIGINS = ("preexisting", "person", "hidden", "agent")
ARTIFACT_CHECKS = ("paths_present", "deps_unchanged", "scope_clean", "marker_present")
CLASS = {"command": "E1", "artifact": "E2", "trajectory": "E3", "judge": "E4", "attributed": "E5"}
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
    for group in ("requirements", "forbidden_effects", "process"):
        for i, r in enumerate(d.get(group, [])):
            for k in ("id", "text", "evidence"):
                if k not in r:
                    raise LedgerError("eval.definition", f"{group}[{i}].{k} missing")
            for j, e in enumerate(r["evidence"]):
                where = f"{group}[{i}].evidence[{j}]"
                kind = e.get("kind")
                if kind == "command":
                    if not isinstance(e.get("run"), list) or not e["run"]:
                        raise LedgerError("eval.definition", f"{where}.run must be a non-empty list")
                    if e.get("origin", "preexisting") not in ORIGINS:
                        raise LedgerError("eval.definition", f"{where}.origin must be one of {ORIGINS}")
                elif kind == "artifact":
                    if e.get("check") not in ARTIFACT_CHECKS:
                        raise LedgerError("eval.definition", f"{where}.check must be one of {ARTIFACT_CHECKS}")
                elif kind == "attributed":
                    if "source" not in e:
                        raise LedgerError("eval.definition", f"{where}.source missing")
                elif kind in ("trajectory", "judge"):
                    if "check" not in e and "question" not in e:
                        raise LedgerError("eval.definition", f"{where} needs check or question")
                else:
                    raise LedgerError("eval.definition", f"{where}.kind must be one of {EVIDENCE_KINDS}")
    scope = d.get("scope", {})
    if not isinstance(scope, dict) or not isinstance(scope.get("allowed_paths", []), list):
        raise LedgerError("eval.definition", "scope.allowed_paths must be a list")
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


# ---- project facts -----------------------------------------------------------------------------------

def detect_test_command(root: Path) -> list[str] | None:
    """The command the project itself declares for its tests, or None."""
    pkg = root / "package.json"
    if pkg.is_file():
        try:
            if json.loads(pkg.read_text()).get("scripts", {}).get("test"):
                return ["npm", "test"]
        except json.JSONDecodeError:
            pass
    py = root / "pyproject.toml"
    if py.is_file() and re.search(r"pytest", py.read_text()):
        return ["pytest", "-q"]
    mk = root / "Makefile"
    if mk.is_file() and re.search(r"^test:", mk.read_text(), re.M):
        return ["make", "test"]
    return None


def _has_command_evidence(d: dict) -> bool:
    return any(e.get("kind") == "command" for g in ("requirements", "forbidden_effects") for r in d.get(g, []) for e in r["evidence"])


def _changes(ws: Workspace, subject: dict) -> dict | None:
    """Changed files and line counts of a git_commit subject against its parent (or scope.base); None otherwise."""
    if subject["kind"] != "git_commit":
        return None
    ref = subject["ref"]
    base = subject.get("base") or f"{ref}^"
    try:
        _git(ws.root, "rev-parse", "--verify", "--quiet", base)
    except subprocess.CalledProcessError:
        return {"base": None, "files": {}, "parent_missing": True}
    out = _git(ws.root, "diff", "--numstat", base, ref)
    files = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            add, rm, name = parts
            files[name] = (0 if add == "-" else int(add)) + (0 if rm == "-" else int(rm))
    return {"base": base, "files": files}


def _inside(path: str, allowed: list[str]) -> bool:
    return any(path == a or path.startswith(a if a.endswith("/") else a + "/") for a in allowed)


def _deps(ws: Workspace, ref: str | None) -> str | None:
    try:
        text = _git(ws.root, "show", f"{ref}:package.json") if ref else (ws.root / "package.json").read_text()
    except (subprocess.CalledProcessError, OSError):
        return None
    try:
        pkg = json.loads(text)
    except json.JSONDecodeError:
        return None
    return json.dumps({k: pkg.get(k) for k in ("dependencies", "devDependencies", "peerDependencies")}, sort_keys=True)


def _artifact(ws: Workspace, root: Path, subject: dict, scope: dict, changes: dict | None, spec: dict) -> dict:
    out = {"kind": "artifact", "check": spec["check"], "time": sessions.now()}
    check = spec["check"]
    if check == "paths_present":
        missing = [p for p in spec.get("paths", []) if not (root / p).exists()]
        out.update(paths=spec.get("paths", []), missing=missing, outcome="pass" if spec.get("paths") and not missing else ("indeterminate" if not spec.get("paths") else "fail"))
    elif check == "deps_unchanged":
        if changes is None or changes.get("parent_missing"):
            out.update(outcome="indeterminate", error="no base commit to compare dependency blocks against")
        else:
            before, after = _deps(ws, changes["base"]), _deps(ws, subject["ref"])
            out.update(outcome="pass" if before == after else "fail", before_sha256=digest.sha256_bytes((before or "").encode()), after_sha256=digest.sha256_bytes((after or "").encode()))
    elif check == "scope_clean":
        allowed = spec.get("allowed_paths") or scope.get("allowed_paths") or []
        if changes is None or changes.get("parent_missing"):
            out.update(outcome="indeterminate", error="no base commit to diff against")
        elif not allowed:
            out.update(outcome="indeterminate", error="no allowed_paths in the definition scope")
        else:
            unbound = {f: n for f, n in changes["files"].items() if not _inside(f, allowed)}
            lines = sum(unbound.values())
            out.update(allowed_paths=allowed, unbound_files=sorted(unbound), unbound_lines=lines, outcome="pass" if lines <= int(spec.get("max_unbound_lines", 0)) else "fail")
    elif check == "marker_present":
        marker = spec.get("marker", "")
        paths = spec.get("paths") or (sorted(changes["files"]) if changes else [])
        found = [p for p in paths if (root / p).is_file() and marker and marker in (root / p).read_text(errors="replace")]
        out.update(marker=marker, searched=paths, found=found, outcome="pass" if found else "fail")
    return out


def _run_command(root: Path, spec: dict) -> dict:
    start = time.monotonic()
    out = {"kind": "command", "run": spec["run"], "origin": spec.get("origin", "preexisting"), "time": sessions.now()}
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


def _evaluate(ws: Workspace, root: Path, subject: dict, scope: dict, changes: dict | None, items: list[dict], observations: list[dict], limitations: list[str]) -> list[dict]:
    results = []
    for item in items:
        evidence = []
        for spec in item["evidence"]:
            kind = spec["kind"]
            if kind == "command":
                evidence.append(_run_command(root, spec))
            elif kind == "artifact":
                evidence.append(_artifact(ws, root, subject, scope, changes, spec))
            elif kind in ("trajectory", "judge"):
                evidence.append({"kind": kind, **{k: v for k, v in spec.items() if k != "kind"}, "outcome": "indeterminate", "error": f"{kind} evidence is not collected by this version"})
            else:
                for obs in observations:
                    if obs.get("requirement") == item["id"] and obs.get("source") == spec["source"]:
                        evidence.append({"kind": "attributed", **obs})
        # An agent-written test is not self-certifying: it counts only beside an independent fact that the change is what it tests.
        independent = [e for e in evidence if e["kind"] in ("artifact", "trajectory") and e["outcome"] == "pass"]
        for e in evidence:
            if e["kind"] == "command" and e.get("origin") == "agent" and e["outcome"] == "pass" and not independent:
                e["outcome"] = "indeterminate"
                e["note"] = "test written by the change under test; needs an artifact or trajectory fact beside it"
                limitations.append(f"{item['id']}: tests written by the change under test")
        outcomes = [e["outcome"] for e in evidence]
        passing = [e for e in evidence if e["outcome"] == "pass"]
        strongest = min((CLASS[e["kind"]] for e in passing), default=None)
        results.append({"id": item["id"], "text": item["text"], "required": item.get("required", True),
                        "status": _status(outcomes), "strongest": strongest, "evidence": evidence})
    return results


def freeze(ws: Workspace, *, subject_kind: str, subject_ref: str, definition: dict, ask_id: str | None = None, contract: dict | None = None,
           attested_only: bool = False) -> dict:
    validate_definition(definition)
    if subject_kind not in KINDS:
        raise LedgerError("subject.kind", subject_kind)
    scope = dict(definition.get("scope", {}))
    root = Path(subject_ref) if subject_kind == "worktree" else ws.root
    test_command = scope.get("test_command") or detect_test_command(root)
    if test_command:
        scope["test_command"] = test_command
    if test_command and not _has_command_evidence(definition) and not attested_only:
        raise LedgerError("eval.no_command_evidence", f"the project declares a test command ({' '.join(test_command)}) but the definition runs nothing; "
                          "add command evidence or pass --attested-only to record an attestation-only Eval")
    eval_id = ids.new_id("evl")
    frozen = {**definition, "scope": scope, "eval_id": eval_id, "subject": {"kind": subject_kind, "ref": subject_ref},
              "basis": {"ask_id": ask_id} if ask_id else {"contract": contract or {}}, "attested_only": bool(attested_only), "frozen_at": sessions.now()}
    ref = store.publish(ws, f"evals/{eval_id}.definition.json", store.canonical(frozen) + b"\n", role="eval_definition")
    return {"eval_id": eval_id, "definition": ref}


def _floor(required: list[dict]) -> str | None:
    """The weakest 'strongest' class among the required requirements that passed; None when nothing passed."""
    classes = [r["strongest"] for r in required if r["strongest"]]
    return max(classes) if classes else None


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
    scope = definition.get("scope", {})
    before = subject_digest(ws, subject["kind"], subject["ref"])
    root = Path(subject["ref"]) if subject["kind"] == "worktree" else ws.root
    changes = _changes(ws, subject)
    limitations = ["attributed observations are not independently verified", "commands are caller-selected"]
    requirements = _evaluate(ws, root, subject, scope, changes, definition.get("requirements", []), observations or [], limitations)
    forbidden = _evaluate(ws, root, subject, scope, changes, definition.get("forbidden_effects", []), observations or [], limitations)
    process = _evaluate(ws, root, subject, scope, changes, definition.get("process", []), observations or [], limitations)
    after = subject_digest(ws, subject["kind"], subject["ref"])
    basis = dict(definition["basis"])
    if basis.get("ask_id"):
        from ringframe import ask as _ask  # local import: ask depends on sessions/profiles, not on evaluate
        rec = _ask._by_id(ws).get(basis["ask_id"])
        basis["submission"] = _ask.submission_grade(rec) if rec and rec["compiled"] else "unobserved"
        limitations.append(f"submission of the compiled prompt: {basis['submission']}")
    observed = [f["id"] for f in forbidden if f["status"] == "covered-fail"]
    required = [r for r in requirements if r["required"]]
    floor = _floor(required)
    if before != after:
        verdict = "incomplete"
        limitations.append("subject.changed")
    elif any(r["status"] == "covered-fail" for r in required) or observed:
        verdict = "drifted"
    elif all(r["status"] == "covered-pass" for r in required) and all(f["status"] == "covered-pass" for f in forbidden):
        # attestation-only: no required requirement has any independent evidence (command, artifact, trajectory, judge)
        attested_only = bool(required) and all(r["strongest"] == "E5" for r in required)
        verdict = "attested" if attested_only else "aligned"
        if attested_only:
            limitations.append("attested: every required requirement rests on the person's word alone; nothing ran")
        elif floor == "E5":
            limitations.append("evidence floor E5: " + ", ".join(r["id"] for r in required if r["strongest"] == "E5") + " rest on the person's word alone")
    else:
        verdict = "incomplete"
    # drift, measured from the artifact (ADR-0009)
    allowed = scope.get("allowed_paths") or []
    unbound = {f: n for f, n in (changes or {}).get("files", {}).items() if allowed and not _inside(f, allowed)}
    total_lines = sum((changes or {}).get("files", {}).values()) or 0
    unmet = [r["id"] for r in required if r["status"] != "covered-pass"]
    drift = {"commission": {"rate": (sum(unbound.values()) / total_lines) if total_lines and allowed else (0.0 if allowed else None),
                            "unbound_files": sorted(unbound), "unbound_lines": sum(unbound.values()), "changed_files": sorted((changes or {}).get("files", {})) if changes else None},
             "omission": {"rate": (len(unmet) / len(required)) if required else 0.0, "unmet": unmet},
             "process": {p["id"]: p["status"] for p in process}}
    if not allowed:
        limitations.append("commission drift not measured: the definition declares no scope.allowed_paths")
    record = {"schema": "ringframe.eval/1", "eval_id": eval_id, "basis": basis,
              "definition": {"path": f"evals/{eval_id}.definition.json", "sha256": definition_sha},
              "subject": {**subject, "sha256_before": before, "sha256_after": after},
              "requirements": requirements, "forbidden_effects": forbidden, "process": process, "verdict": verdict, "evidence_floor": floor, "drift": drift,
              "freshness": definition.get("freshness", {"max_age": "PT24H"}), "limitations": limitations, "time": sessions.now()}
    ref = store.publish(ws, f"evals/{eval_id}.json", store.canonical(record) + b"\n", role="eval_record")
    counts = {k: sum(1 for r in requirements if r["status"] == k.replace("_", "-")) for k in ("covered_pass", "covered_fail", "uncovered", "indeterminate")}
    ask_id = definition["basis"].get("ask_id")
    ev = {"schema": store.SCHEMA, "event_id": ids.new_id("evt"), "type": "eval.completed", "time": record["time"], "id": eval_id,
          "actor": {"kind": "human", "id": "local-user", "authority": "interactive"},
          "links": [{"rel": "evaluates", "id": ask_id}] if ask_id else [],
          "data": {"subject": record["subject"], "definition_sha256": definition_sha, "verdict": verdict, "evidence_floor": floor, "counts": counts,
                   "forbidden_effects_observed": observed, "drift": {"commission_rate": drift["commission"]["rate"], "omission_rate": drift["omission"]["rate"]}, "artifact": ref,
                   "definition": {"role": "eval_definition", "path": record["definition"]["path"], "bytes": len(raw), "sha256": definition_sha},
                   "limitations": limitations}}
    schema.validate_event(ev)
    store.append(ws, ev)
    return record


def scaffold(ws: Workspace, *, subject_ref: str, title: str, ask_id: str | None) -> dict:
    """A draft definition built from facts: the project's test command, the commit's changed paths, artifact checks.

    The skill adds requirements the prompt states and attributed evidence only for what no fact can see."""
    test_command = detect_test_command(ws.root)
    changes = _changes(ws, {"kind": "git_commit", "ref": subject_ref}) or {"files": {}}
    dirs = sorted({(f.split("/")[0] + "/") if "/" in f else f for f in changes.get("files", {})})
    allowed = [d for d in dirs if d.endswith("/")] or dirs
    tests_existed = bool(changes.get("base")) and any(n.startswith(("tests/", "test/", "spec/")) for n in _git(ws.root, "ls-tree", "-r", "--name-only", changes["base"]).splitlines()) if changes.get("base") else False
    req_evidence = []
    if test_command:
        req_evidence.append({"kind": "command", "run": test_command, "pass_when": {"exit_code": 0}, "origin": "preexisting" if tests_existed else "agent"})
    req_evidence.append({"kind": "attributed", "source": "human:local-user"})
    d = {"schema": DEFINITION_SCHEMA, "scope": {"allowed_paths": allowed, **({"test_command": test_command} if test_command else {})},
         "requirements": [{"id": "R1", "text": title, "required": True, "evidence": req_evidence}],
         "forbidden_effects": [{"id": "F1", "text": "no new dependency", "evidence": [{"kind": "artifact", "check": "deps_unchanged"}]},
                               {"id": "F2", "text": "no change outside the allowed paths", "evidence": [{"kind": "artifact", "check": "scope_clean", "max_unbound_lines": 0}]}],
         "freshness": {"max_age": "PT24H"}}
    if ask_id:
        d["basis_hint"] = {"ask_id": ask_id}
    return d


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
                    "verdict": rec.get("verdict") if rec else None, "evidence_floor": rec.get("evidence_floor") if rec else None,
                    "completed_at": rec.get("time") if rec else None,
                    "path": f"evals/{eval_id}.json" if rec else f"evals/{eval_id}.definition.json"})
    return out
