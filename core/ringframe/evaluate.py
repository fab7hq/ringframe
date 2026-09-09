"""Eval: a judged verdict with confidence over every open Ask.

The CLI records facts exactly: the open Asks, the anchor, the subject digest, the changed files, how many
unrecorded prompts followed each Ask, which judgements were submitted. Sub-agents of the eval skill judge:
one reconstructs the effective intent from the Asks; at least three, from distinct angles, vote per item and
classify each changed path. The CLI aggregates majorities and agreement into `verdict` and `confidence`.
RingFrame runs none of the project's commands and knows nothing about its stack."""

import json
import re
import subprocess
from pathlib import Path

from ringframe import digest, ids, schema, sessions, store
from ringframe.store import LedgerError
from ringframe.workspace import Workspace

BRIEF_SCHEMA = "ringframe.eval-brief/1"
INTENT_SCHEMA = "ringframe.eval-intent/1"
JUDGEMENT_SCHEMA = "ringframe.eval-judgement/1"
RECORD_SCHEMA = "ringframe.eval/1"
KINDS = ("git_commit", "worktree")
ITEM_STATUS = ("active", "revised", "withdrawn")
VOTES = ("yes", "no", "unknown")
CLASSIFICATIONS = ("required", "consequence", "unexplained")
INDEPENDENCE = ("sub_agent", "shared_context")
MIN_JUDGES = 3


class NeedsInput(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
        self.candidates = []


def _git(root, *args) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout


def subject_digest(ws: Workspace, kind: str, ref: str) -> str:
    if kind == "git_commit":
        prefix = _git(ws.root, "rev-parse", "--show-prefix").strip()
        if prefix:
            # Hash only this project, including the empty tree when absent in ref.
            listing = _git(ws.root, "ls-tree", "--full-tree", "-z", ref, "--", f":(top,literal){prefix.rstrip('/')}")
            return digest.sha256_bytes(listing.encode())
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
    raise LedgerError("subject.kind", f"{kind!r} not in {KINDS}")


def default_subject(ws: Workspace) -> tuple[str, str]:
    """The current commit when the tree is clean, else the worktree."""
    if _git(ws.root, "status", "--porcelain", "--", ".").strip():
        return "worktree", str(ws.root)
    return "git_commit", _git(ws.root, "rev-parse", "HEAD").strip()


# ---- facts ------------------------------------------------------------------------------------------------

def _anchor(ws: Workspace, asks: list[dict], explicit: str | None) -> dict:
    if explicit:
        return {"kind": "explicit", "ref": explicit, "seal_id": None}
    seals = [e for e in store.events(ws) if e["type"] == "seal.created"]
    if seals and seals[-1]["data"]["subject"].get("kind") == "git_commit":
        return {"kind": "seal", "ref": seals[-1]["data"]["subject"]["ref"], "seal_id": seals[-1]["id"]}
    base = next((a["base_commit"] for a in asks if a.get("base_commit")), None)
    if base:
        return {"kind": "ask_base", "ref": base, "seal_id": None}
    raise NeedsInput("eval.anchor_unknown: no Seal and no Ask with a base commit; pass --anchor <commit>")


def _rename_target(path: str) -> str:
    path = re.sub(r"\{[^{}]* => ([^{}]*)\}", r"\1", path)
    return path.split(" => ")[-1]


def _count_lines(p: Path) -> int:
    try:
        return p.read_bytes().count(b"\n")
    except OSError:
        return 0


def _changes(ws: Workspace, anchor: str, subject: dict) -> dict:
    """Files changed between the anchor and the subject, with line counts. Never their content."""
    target = [subject["ref"]] if subject["kind"] == "git_commit" else []
    root = ws.root if subject["kind"] == "git_commit" else Path(subject["ref"])
    status = {}
    for line in _git(root, "diff", "--relative", "--name-status", "-M", anchor, *target, "--", ".").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            status[parts[-1]] = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed"}.get(parts[0][0], parts[0][0].lower())
    files = {}
    for line in _git(root, "diff", "--relative", "--numstat", "-M", anchor, *target, "--", ".").splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            add, rm, name = parts
            name = _rename_target(name)
            files[name] = {"path": name, "status": status.get(name, "modified"),
                           "added": 0 if add == "-" else int(add), "removed": 0 if rm == "-" else int(rm)}
    if subject["kind"] == "worktree":
        for name in _git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0"):
            if name and name not in files:
                files[name] = {"path": name, "status": "added", "added": _count_lines(root / name), "removed": 0}
    ordered = [files[k] for k in sorted(files)]
    return {"files": ordered, "total_added": sum(f["added"] for f in ordered), "total_removed": sum(f["removed"] for f in ordered)}


def _unrecorded_prompts(ws: Workspace, asks: list[dict]) -> list[int]:
    """How many prompts that were neither /rf: invocations nor observed Ask submissions followed each Ask."""
    submitted = {e["data"]["prompt_sha256"] for e in store.events(ws) if e["type"] == "ask.submission"}
    times = []
    for path in sorted((ws.rf_dir / "sessions").glob("*/*/prompts.jsonl")):
        for line in path.read_bytes().splitlines():
            rec = json.loads(line)
            if "prompt" not in rec and rec.get("sha256") not in submitted:
                times.append(rec.get("time", ""))
    counts = []
    for i, a in enumerate(asks):
        start, end = a["time"], asks[i + 1]["time"] if i + 1 < len(asks) else "9"
        counts.append(sum(1 for t in times if start <= t < end))
    return counts


def _previous(ws: Workspace, eval_id: str, ask_ids: list[str]) -> dict | None:
    """The latest completed Eval whose basis shares an Ask with this one: the loop's memory."""
    recs = [r for r in list_records(ws) if r["state"] == "completed" and r["eval_id"] != eval_id and set(r["basis"]["asks"]) & set(ask_ids)]
    return load_record(ws, recs[-1]["eval_id"]) if recs else None


def open_eval(ws: Workspace, *, anchor: str | None = None, subject_kind: str | None = None, subject_ref: str | None = None, actor: dict | None = None) -> dict:
    """Write the facts-only brief over every open Ask and append `eval.opened`."""
    from ringframe import ask as _ask  # ask does not import evaluate
    asks = _ask.open_asks(ws)
    if not asks:
        raise LedgerError("eval.no_open_ask", "nothing to evaluate: every Ask is sealed or cancelled")
    if bool(subject_kind) != bool(subject_ref):
        raise LedgerError("subject.kind", "--subject-kind and --subject-ref go together")
    if subject_kind and subject_kind not in KINDS:
        raise LedgerError("subject.kind", f"{subject_kind!r} not in {KINDS}")
    try:
        _git(ws.root, "rev-parse", "--git-dir")
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise LedgerError("eval.no_git", "Eval reads the Git delta; this workspace is not a Git repository") from None
    kind, ref = (subject_kind, subject_ref) if subject_kind else default_subject(ws)
    ask_ids = [a["ask_id"] for a in asks]
    dangling = [r for r in list_records(ws) if r["state"] == "opened" and r["basis"]["asks"] == ask_ids]
    if dangling:
        raise LedgerError("eval.already_open", f"{dangling[-1]['eval_id']} is open over the same Asks and not closed; close it or continue with it")
    anchor_d = _anchor(ws, asks, anchor)
    try:
        _git(ws.root, "rev-parse", "--verify", "--quiet", f"{anchor_d['ref']}^{{commit}}")
    except subprocess.CalledProcessError:
        raise LedgerError("eval.anchor_missing", f"{anchor_d['ref']} is not a commit in this workspace") from None
    subject = {"kind": kind, "ref": ref, "sha256": subject_digest(ws, kind, ref)}
    eval_id = ids.new_id("evl")
    counts = _unrecorded_prompts(ws, asks)
    previous = [{"eval_id": r["eval_id"], "verdict": r["verdict"], "confidence": r["confidence"], "time": r["completed_at"]}
                for r in list_records(ws) if r["state"] == "completed" and set(r["basis"]["asks"]) & {a["ask_id"] for a in asks}]
    limitations = ["the brief describes the ledger and the Git delta only; RingFrame runs none of the project's commands",
                   "plain prompts are counted, never stored; changes no Ask explains may follow an unrecorded instruction"]
    if kind == "worktree":
        limitations.append("subject is the uncommitted worktree")
    brief = {"schema": BRIEF_SCHEMA, "eval_id": eval_id, "time": sessions.now(), "workspace": ws.describe(), "anchor": anchor_d, "subject": subject,
             "asks": [{"ask_id": a["ask_id"], "order": i + 1, "title": a["title"], "prompt_path": a["prompt"]["path"], "compiled": a["time"],
                       "confirmed": a["confirmed_at"], "submission": a["submission"], "links": a["links"], "unrecorded_prompts_after": counts[i]}
                      for i, a in enumerate(asks)],
             "changes": _changes(ws, anchor_d["ref"], subject), "previous_evals": previous, "limitations": limitations}
    ref_ = store.publish(ws, f"evals/{eval_id}/brief.json", store.canonical(brief) + b"\n", role="eval_brief")
    data = {"brief": ref_, "basis": {"asks": [a["ask_id"] for a in asks], "unrecorded_prompts": sum(counts)}, "anchor": anchor_d, "subject": subject}
    ev = _event("eval.opened", eval_id, actor, data, [{"rel": "evaluates", "id": a["ask_id"]} for a in asks])
    store.append(ws, ev)
    return {"eval_id": eval_id, "brief_path": str(ws.rf_dir / ref_["path"]), "brief": ref_, **data,
            "changes": {"files": len(brief["changes"]["files"]), "added": brief["changes"]["total_added"], "removed": brief["changes"]["total_removed"]}}


def _event(type_, id_, actor, data, links):
    ev = {"schema": store.SCHEMA, "event_id": ids.new_id("evt"), "type": type_, "time": sessions.now(), "id": id_,
          "actor": actor or {"kind": "human", "id": "local-user", "authority": "interactive"}, "links": links, "data": data}
    schema.validate_event(ev)
    return ev


# ---- judgements ---------------------------------------------------------------------------------------------

def _need(cond, code, msg):
    if not cond:
        raise LedgerError(code, msg)


def _judge(j, code, where):
    _need(isinstance(j, dict) and isinstance(j.get("host"), str) and isinstance(j.get("angle"), str), code, f"{where}.judge needs host and angle")
    _need(j.get("independence") in INDEPENDENCE, code, f"{where}.judge.independence must be one of {INDEPENDENCE}")


def validate_intent(intent: dict, brief_sha256: str, ask_ids: list[str]) -> None:
    code = "eval.intent"
    _need(isinstance(intent, dict) and intent.get("schema") == INTENT_SCHEMA, code, f"schema must be {INTENT_SCHEMA}")
    _need(intent.get("brief_sha256") == brief_sha256, "eval.brief_mismatch", "intent.brief_sha256 is not this Eval's brief")
    _judge(intent.get("judge"), code, "intent")
    items = intent.get("items")
    _need(isinstance(items, list) and items, code, "items must be a non-empty list")
    seen = set()
    for i, it in enumerate(items):
        _need(isinstance(it, dict) and isinstance(it.get("id"), str) and it["id"] not in seen, code, f"items[{i}].id missing or duplicate")
        seen.add(it["id"])
        _need(isinstance(it.get("text"), str) and it["text"].strip(), code, f"items[{i}].text missing")
        _need(it.get("ask_id") in ask_ids, code, f"items[{i}].ask_id is not an open Ask of this Eval")
        _need(it.get("status") in ITEM_STATUS, code, f"items[{i}].status must be one of {ITEM_STATUS}")


def validate_judgement(j: dict, brief_sha256: str, intent_sha256: str, items: list[dict], where: str, changed_paths: list[str] = ()) -> None:
    code = "eval.judgement"
    _need(isinstance(j, dict) and j.get("schema") == JUDGEMENT_SCHEMA, code, f"{where}: schema must be {JUDGEMENT_SCHEMA}")
    _need(j.get("brief_sha256") == brief_sha256, "eval.brief_mismatch", f"{where}: brief_sha256 is not this Eval's brief")
    _need(j.get("intent_sha256") in (None, intent_sha256), "eval.brief_mismatch", f"{where}: intent_sha256 is not this Eval's intent")
    _judge(j.get("judge"), code, where)
    ids_ = {it["id"] for it in items}
    active = {it["id"] for it in items if it["status"] == "active"}
    votes = j.get("votes")
    _need(isinstance(votes, list), code, f"{where}.votes must be a list")
    voted = set()
    for i, v in enumerate(votes):
        _need(isinstance(v, dict) and v.get("item") in ids_, code, f"{where}.votes[{i}].item is not an intent item")
        _need(v.get("vote") in VOTES, code, f"{where}.votes[{i}].vote must be one of {VOTES}")
        voted.add(v["item"])
    _need(active <= voted, code, f"{where}: no vote for active items {sorted(active - voted)}")
    classified = set()
    for i, d in enumerate(j.get("drift", [])):
        _need(isinstance(d, dict) and isinstance(d.get("path"), str) and d["path"], code, f"{where}.drift[{i}].path missing")
        _need(d.get("classification") in CLASSIFICATIONS, code, f"{where}.drift[{i}].classification must be one of {CLASSIFICATIONS}")
        classified.add(d["path"])
    missing = [p for p in changed_paths if p not in classified]
    _need(not missing, code, f"{where}: no drift classification for changed paths {missing}")
    for k in ("basis_notes", "commands_run"):
        _need(isinstance(j.get(k, []), list), code, f"{where}.{k} must be a list")


def _majority(values: list[str], tie: str) -> tuple[str, float]:
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    best = max(counts.values())
    winners = [k for k, n in counts.items() if n == best]
    return (winners[0] if len(winners) == 1 else tie), best / len(values)


def _aggregate(items: list[dict], judgements: list[dict], changed_paths: list[str]) -> dict:
    active = [it for it in items if it["status"] == "active"]
    table = []
    for it in active:
        votes = [{"angle": j["judge"]["angle"], "vote": next(v["vote"] for v in j["votes"] if v["item"] == it["id"]),
                  "reason": next((v.get("reason", "") for v in j["votes"] if v["item"] == it["id"]), "")} for j in judgements]
        maj, agr = _majority([v["vote"] for v in votes], "unknown")
        table.append({**it, "majority": maj, "agreement": round(agr, 2), "votes": votes})
    by_path = {}
    for j in judgements:
        for d in j.get("drift", []):
            by_path.setdefault(d["path"], []).append({"angle": j["judge"]["angle"], "classification": d["classification"], "finding": d.get("finding", "")})
    paths = []
    for path in sorted(by_path):
        # Every judge classifies every changed path (validated); a judge silent on a path outside the brief counts as
        # `required` there, so one loud judge cannot make a finding unanimous. Agreement is always over every judge.
        votes = [f["classification"] for f in by_path[path]] + ["required"] * (len(judgements) - len(by_path[path]))
        maj, agr = _majority(votes, "unexplained")
        paths.append({"path": path, "classification": maj, "agreement": round(agr, 2), "mentions": len(by_path[path]), "findings": by_path[path]})
    unmentioned = [p for p in changed_paths if p not in by_path]
    commission = [p for p in paths if p["classification"] == "unexplained"]
    omission = [it["id"] for it in table if it["majority"] != "yes"]
    if not active:
        verdict = "incomplete"
    elif any(it["majority"] == "no" for it in table) or commission:
        verdict = "drifted"
    elif all(it["majority"] == "yes" for it in table):
        verdict = "aligned"
    else:
        verdict = "incomplete"
    # every active item decides; a path decides when its majority is a finding or when any judge dissented from `required`
    deciding = [it["agreement"] for it in table] + [p["agreement"] for p in paths if p["classification"] != "required" or p["agreement"] < 1.0]
    return {"verdict": verdict, "confidence": round(min(deciding), 2) if deciding else 0.0, "items": table,
            "drift": {"omission": omission, "commission": [{k: p[k] for k in ("path", "classification", "agreement")} for p in commission],
                      "paths": paths, "unmentioned": unmentioned}}


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9_]+", text.lower()) if len(w) > 2}


def _match(item: dict, candidates: list[dict]) -> dict | None:
    """The previous item this one continues: same id and Ask, else same normalized text, else the best token overlap
    (Jaccard >= 0.5) within the same Ask. Judges reword; the record says how each match was made."""
    same_ask = [c for c in candidates if c.get("ask_id") == item.get("ask_id")]
    for c in same_ask:
        if c["id"] == item["id"]:
            return c
    for c in candidates:
        if _norm(c["text"]) == _norm(item["text"]):
            return c
    a = _tokens(item["text"])
    best, score = None, 0.0
    for c in same_ask:
        b = _tokens(c["text"])
        j = len(a & b) / len(a | b) if a | b else 0.0
        if j > score:
            best, score = c, j
    return best if score >= 0.5 else None


def _delta(current: dict, previous: dict | None) -> dict | None:
    if previous is None:
        return None
    prev_items = list(previous["items"])
    closed, opened, new = [], [], []
    for it in current["items"]:
        before = _match(it, prev_items)
        if before is None:
            new.append(it["text"])
            if it["majority"] != "yes":
                opened.append(it["text"])
        elif it["majority"] == "yes" and before["majority"] != "yes":
            closed.append(it["text"])
        elif it["majority"] != "yes" and before["majority"] == "yes":
            opened.append(it["text"])
    paths = lambda rec: {c["path"] for c in rec["drift"]["commission"]}
    return {"closed": sorted(closed), "opened": sorted(opened), "new_items": sorted(new),
            "commission_removed": sorted(paths(previous) - paths(current)), "commission_added": sorted(paths(current) - paths(previous)),
            "matching": "items matched to the previous Eval by id within the same Ask, then normalized text, then token overlap >= 0.5 within the same Ask"}


def close_eval(ws: Workspace, eval_id: str, *, intent: dict, judgements: list[dict], actor: dict | None = None) -> dict:
    """Validate the intent and the judgements, aggregate, append `eval.completed`."""
    brief_path = ws.rf_dir / f"evals/{eval_id}/brief.json"
    if not brief_path.exists() or not any(e["type"] == "eval.opened" and e["id"] == eval_id for e in store.events(ws)):
        raise LedgerError("eval.missing", eval_id)
    if (ws.rf_dir / f"evals/{eval_id}/record.json").exists():
        raise LedgerError("ledger.immutable", f"evals/{eval_id}/record.json")
    brief_sha = digest.sha256_file(brief_path)
    brief = json.loads(brief_path.read_bytes())
    ask_ids = [a["ask_id"] for a in brief["asks"]]
    if len(judgements) < MIN_JUDGES:
        raise LedgerError("eval.too_few_judges", f"{len(judgements)} judgements; at least {MIN_JUDGES} independent angles are required")
    validate_intent(intent, brief_sha, ask_ids)
    intent_bytes = store.canonical(intent) + b"\n"
    intent_sha = digest.sha256_bytes(intent_bytes)
    changed_paths = [f["path"] for f in brief["changes"]["files"]]
    for n, j in enumerate(judgements, 1):
        validate_judgement(j, brief_sha, intent_sha, intent["items"], f"judgement[{n}]", changed_paths)
    subject = brief["subject"]
    now_digest = subject_digest(ws, subject["kind"], subject["ref"])
    limitations = [f"the verdict is a judgement by {len(judgements)} sub-agents; agreement is its confidence, nothing here is certain",
                   "RingFrame ran none of the project's commands; commands_run in a judgement is that judge's own report"]
    agg = _aggregate(intent["items"], judgements, [f["path"] for f in brief["changes"]["files"]])
    if now_digest != subject["sha256"]:
        agg["verdict"] = "incomplete"
        limitations.append("subject.changed: the subject changed between open and close")
    if not agg["items"]:
        limitations.append("no active intent item: nothing to judge")
    if any(j["judge"]["independence"] == "shared_context" for j in judgements):
        limitations.append("some judges shared one context; their agreement overstates independence")
    n_unrecorded = sum(a["unrecorded_prompts_after"] for a in brief["asks"])
    if n_unrecorded:
        limitations.append(f"{n_unrecorded} unrecorded prompts followed the open Asks; unexplained changes may follow them")
    intent_ref = store.publish(ws, f"evals/{eval_id}/intent.json", intent_bytes, role="eval_intent")
    j_refs = [store.publish(ws, f"evals/{eval_id}/judgement-{n}.json", store.canonical(j) + b"\n", role="eval_judgement") for n, j in enumerate(judgements, 1)]
    previous = _previous(ws, eval_id, ask_ids)
    record = {"schema": RECORD_SCHEMA, "eval_id": eval_id, "time": sessions.now(),
              "basis": {"asks": ask_ids, "anchor": brief["anchor"], "unrecorded_prompts": n_unrecorded},
              "subject": {**subject, "sha256_at_close": now_digest}, "brief": {"path": f"evals/{eval_id}/brief.json", "sha256": brief_sha},
              "intent": {"path": intent_ref["path"], "sha256": intent_sha, "judge": intent["judge"], "items": len(intent["items"]), "active": len(agg["items"])},
              "judgements": [{"path": r["path"], "sha256": r["sha256"], "judge": j["judge"]} for r, j in zip(j_refs, judgements)],
              "verdict": agg["verdict"], "confidence": agg["confidence"], "items": agg["items"], "drift": agg["drift"],
              "follows": previous["eval_id"] if previous else None, "delta": _delta(agg, previous), "limitations": limitations}
    ref = store.publish(ws, f"evals/{eval_id}/record.json", store.canonical(record) + b"\n", role="eval_record")
    data = {"basis": record["basis"], "subject": record["subject"], "verdict": record["verdict"], "confidence": record["confidence"],
            "items": {"active": len(agg["items"]), "met": sum(1 for it in agg["items"] if it["majority"] == "yes"), "omission": len(agg["drift"]["omission"])},
            "commission": [c["path"] for c in agg["drift"]["commission"]], "judges": [j["judge"] for j in judgements],
            "intent": intent_ref, "judgements": j_refs, "artifact": ref, "limitations": limitations}
    links = [{"rel": "evaluates", "id": a} for a in ask_ids] + ([{"rel": "supersedes", "id": previous["eval_id"]}] if previous else [])
    store.append(ws, _event("eval.completed", eval_id, actor, data, links))
    return record


def load_record(ws: Workspace, eval_id: str) -> dict | None:
    p = ws.rf_dir / f"evals/{eval_id}/record.json"
    return json.loads(p.read_bytes()) if p.exists() else None


def list_records(ws: Workspace) -> list[dict]:
    """Every Eval in this workspace, opened or completed, oldest first."""
    out = []
    d = ws.rf_dir / "evals"
    for brief_path in sorted(d.glob("*/brief.json"), key=lambda p: json.loads(p.read_bytes())["time"]) if d.exists() else []:
        brief = json.loads(brief_path.read_bytes())
        eval_id = brief["eval_id"]
        rec = load_record(ws, eval_id)
        out.append({"eval_id": eval_id, "state": "completed" if rec else "opened", "opened_at": brief["time"],
                    "basis": {"asks": [a["ask_id"] for a in brief["asks"]]}, "anchor": brief["anchor"], "subject": brief["subject"],
                    "verdict": rec["verdict"] if rec else None, "confidence": rec["confidence"] if rec else None,
                    "completed_at": rec["time"] if rec else None, "path": f"evals/{eval_id}/record.json" if rec else f"evals/{eval_id}/brief.json"})
    return out


def latest_for(ws: Workspace, ask_ids: list[str]) -> dict | None:
    """The latest completed Eval whose basis shares an Ask with the given set."""
    recs = [r for r in list_records(ws) if r["state"] == "completed" and set(r["basis"]["asks"]) & set(ask_ids)]
    return load_record(ws, recs[-1]["eval_id"]) if recs else None
