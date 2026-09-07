"""Ask: persist a compiled intent, then append graded observations (confirmation, cancellation, submission, delivery)."""

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ringframe import digest, ids, profiles, schema, sessions, store
from ringframe.store import LedgerError
from ringframe.workspace import Workspace

HOOK_WINDOW = timedelta(minutes=30)
HANDOFF = """Prompt prepared for {host} ({capability}):
{path}

Open the file, copy its complete contents, and submit them in the
active {host_title} TUI. RingFrame does not observe that submission.
"""
HOST_TITLES = {"claude-code": "Claude Code", "codex": "Codex"}


class NeedsInput(Exception):
    def __init__(self, reason: str, candidates: list[dict]):
        super().__init__(reason)
        self.reason = reason
        self.candidates = candidates


def _event(type_, id_, actor, data, links=()):
    return {"schema": store.SCHEMA, "event_id": ids.new_id("evt"), "type": type_, "time": sessions.now(),
            "id": id_, "actor": actor, "links": list(links), "data": data}


def _actor(actor):
    return actor or {"kind": "human", "id": "local-user", "authority": "interactive"}


def _authorized(ws, actor, capability, effects) -> dict:
    """Interactive humans act by being present. Any other actor needs a pre-authorization record (ADR-0004)."""
    import json
    if actor["kind"] == "human" and actor.get("authority", "interactive") == "interactive":
        return actor
    path = ws.rf_dir / "authorizations" / f"{actor['id']}.json"
    if not path.exists():
        raise NeedsInput(f"authorization required: no record at authorizations/{actor['id']}.json for {actor['kind']}:{actor['id']}", [])
    grant = json.loads(path.read_text())
    allowed = grant.get("allowed", {})
    from datetime import datetime, timezone
    expired = grant.get("expires") and datetime.fromisoformat(str(grant["expires"]).replace("Z", "+00:00")) <= datetime.now(timezone.utc)
    ok = grant.get("actor") == f"{actor['kind']}:{actor['id']}" and capability in allowed.get("capabilities", []) \
        and set(effects) <= set(allowed.get("effects", [])) and not expired
    if not ok:
        raise NeedsInput(f"authorization does not cover {capability} with effects {sorted(effects)} for {actor['kind']}:{actor['id']}", [])
    return {**actor, "authority": f"preauthorized:authorizations/{actor['id']}.json"}


def _normalize_classification(c) -> dict:
    """Accept `approval-gated` for `approval_gated`; the vocabulary itself is unchanged."""
    if not isinstance(c, dict):
        return c
    fix = lambda v: v.replace("-", "_") if isinstance(v, str) else v
    return {k: [fix(x) for x in v] if isinstance(v, list) else fix(v) for k, v in c.items()}


def _staged(staged: Path) -> tuple[bytes, bytes]:
    names = sorted(p.name for p in Path(staged).iterdir()) if Path(staged).is_dir() else None
    if names != ["prompt.txt", "source.txt"]:
        raise LedgerError("ask.staged_dir", "must contain exactly source.txt and prompt.txt")
    out = []
    for name in ("source.txt", "prompt.txt"):
        data = (Path(staged) / name).read_bytes()
        if not data or data.startswith(b"\xef\xbb\xbf"):
            raise LedgerError("ask.staged_file", f"{name} must be non-empty UTF-8 without BOM")
        data.decode("utf-8")
        out.append(data)
    return out[0], out[1]


def compile(ws, *, staged, title, capability, classification, route, host, links=(), limitations=(), actor=None):
    """The only Ask operation that writes artifacts. Appends `ask.compiled`."""
    source, prompt = _staged(staged)
    classification = _normalize_classification(classification)
    host = dict(host)
    provenance = {}
    if not host.get("session_ref"):
        found = sessions.resolve_session(ws, host["name"], source)
        if found:
            host["session_ref"] = found["session_ref"]
            provenance["session_ref_source"] = "capture"
            if not host.get("version") and found.get("host_version"):
                host["version"] = found["host_version"]
                provenance["version_source"] = "capture"
    profile = profiles.for_host(host)
    cap = profiles.capability(profile, capability)
    if cap is None:
        raise LedgerError("ask.capability", f"{capability!r} is not in profile {profile['profile_id']}")
    gated = set(cap.get("requires_explicit_request_for_effects", [])) & set(classification.get("effects", []))
    if gated and route.get("explicit_direct_request") is not True:
        raise LedgerError("ask.route_policy", f"{capability} with effects {sorted(gated)} requires route.explicit_direct_request=true, "
                          "which is only true when the source intent itself asks to skip planning or act immediately; otherwise select native_plan")
    text = prompt.decode("utf-8")
    prefix = cap.get("prompt_prefix")
    if prefix and not text.startswith(prefix):
        raise LedgerError("ask.prompt_prefix", f"{capability} on {host['name']} requires prompt.txt to begin with {prefix!r}")
    if cap.get("max_prompt_chars") and len(text.rstrip("\n")) > cap["max_prompt_chars"]:
        raise LedgerError("ask.prompt_too_long", f"{capability} on {host['name']} allows at most {cap['max_prompt_chars']} characters")
    actor = _authorized(ws, _actor(actor), capability, classification.get("effects", []))
    limitations = list(limitations or []) + list(cap.get("limitations", []))
    if profile["profile_id"] == "unknown":
        limitations.append("qualification gap: no profile for this host and version")
    ask_id = ids.new_id("ask")
    # Provisional references let the event be validated before anything is written.
    source_ref = {"role": "source_intent", "path": f"asks/{ask_id}/source.txt", "bytes": len(source), "sha256": digest.sha256_bytes(source)}
    prompt_ref = {"role": "generated_prompt", "path": f"asks/{ask_id}/prompt.txt", "bytes": len(prompt), "sha256": digest.sha256_bytes(prompt)}
    verified, reason = sessions.source_verified(ws, host["name"], host.get("session_ref"), source)
    if reason:
        limitations.append(f"source_verified unverified: {reason}")
    data = {"title": title, "classification": classification, "selected_capability": capability, "route_explanation": route,
            "host": {"name": host["name"], "version": host.get("version"), "surface": host.get("surface"),
                     "session_ref": host.get("session_ref"), "workspace": ws.describe(), **provenance,
                     "profile_id": profile["profile_id"], "profile_sha256": profiles.sha256(profile["profile_id"].split("@")[0] if profile["host"] else "unknown")},
            "source": source_ref, "prompt": prompt_ref, "source_verified": verified, "limitations": limitations,
            "delivery_mode": cap["delivery_mode"]}
    ev = _event("ask.compiled", ask_id, actor, data, links)
    schema.validate_event(ev)
    assert store.publish(ws, source_ref["path"], source, role="source_intent") == source_ref
    assert store.publish(ws, prompt_ref["path"], prompt, role="generated_prompt") == prompt_ref
    store.append(ws, ev)
    shutil.rmtree(staged)
    return {"ask_id": ask_id, "source": source_ref, "prompt": prompt_ref, "prompt_path": str(ws.rf_dir / prompt_ref["path"]),
            "source_verified": verified, "delivery_mode": data["delivery_mode"]}


def _append(ws, type_, ask_id, data, actor=None):
    ev = _event(type_, ask_id, _actor(actor), data)
    schema.validate_event(ev)
    store.append(ws, ev)
    return {"ask_id": ask_id, **data}


def confirm(ws, ask_id: str, actor=None) -> dict:
    """Record the skill-reported chooser answer. Evidence grade: observed by the skill, not by the host."""
    rec = _record(ws, ask_id)
    if rec["confirmed"]:
        raise LedgerError("ask.already_confirmed", ask_id)
    d = rec["compiled"]["data"]
    actor = _authorized(ws, _actor(actor), d["selected_capability"], d["classification"].get("effects", []))
    surface = profiles.for_host(d["host"]).get("confirmation", {}).get("tool")  # None under the unknown profile: never invent a surface
    return _append(ws, "ask.confirmed", ask_id, {"confirmation": {"observed_by": "skill", "surface": surface}}, actor)


def cancel(ws, ask_id: str, reason=None, actor=None, attributed=False) -> dict:
    rec = _record(ws, ask_id)
    if rec["cancelled"]:
        raise LedgerError("ask.already_cancelled", ask_id)
    a = _actor(actor)
    grade = {"attributed_by": f"{a['kind']}:{a['id']}"} if attributed else {"observed_by": "skill"}
    return _append(ws, "ask.cancelled", ask_id, {"cancellation": grade, **({"reason": reason} if reason else {})}, a)


def submitted(ws, ask_id: str, as_modified=False, actor=None) -> dict:
    """The person attests that they submitted the prompt (possibly edited). Human attestation, not host evidence."""
    rec = _record(ws, ask_id)
    a = _actor(actor)
    d = rec["compiled"]["data"]
    return _append(ws, "ask.submission", ask_id, {"state": "attributed", "observed_by": None, "attributed_by": f"{a['kind']}:{a['id']}",
                                                  "as_modified": bool(as_modified), "host": {"name": d["host"]["name"], "session_ref": d["host"].get("session_ref")},
                                                  "prompt_sha256": d["prompt"]["sha256"]}, a)


def submission_from_capture(ws, host: str, session: str, sha256: str) -> dict | None:
    """A later user prompt whose bytes equal one compiled prompt.txt: host-observed submission.

    Composers drop a file's trailing newline on paste, so that form matches too (recorded as such).
    Unique match only, once per Ask."""
    hits = []
    for ask_id, v in _by_id(ws).items():
        if not v["compiled"] or any(s["data"]["state"] == "observed" for s in v["submissions"]):
            continue
        ref = v["compiled"]["data"]["prompt"]
        if ref["sha256"] == sha256:
            hits.append((ask_id, "exact"))
        elif digest.sha256_bytes((ws.rf_dir / ref["path"]).read_bytes().rstrip(b"\n")) == sha256:
            hits.append((ask_id, "trailing_newline_dropped"))
    if len(hits) != 1:
        return None
    ask_id, match = hits[0]
    return _append(ws, "ask.submission", ask_id, {"state": "observed", "observed_by": "hook:UserPromptSubmit", "attributed_by": None,
                                                  "as_modified": False, "host": {"name": host, "session_ref": session}, "prompt_sha256": sha256,
                                                  "match": match})


def prompt_text(ws, ask_id: str) -> str:
    return (ws.rf_dir / _record(ws, ask_id)["compiled"]["data"]["prompt"]["path"]).read_text(encoding="utf-8")


def _by_id(ws) -> dict:
    """ask_id -> {"compiled", "confirmed", "cancelled", "delivery": event|None, "submissions": [events]}."""
    out = {}
    for ev in store.events(ws):
        if ev["type"].startswith("ask."):
            rec = out.setdefault(ev["id"], {"compiled": None, "confirmed": None, "cancelled": None, "delivery": None, "submissions": []})
            kind = ev["type"].split(".")[1]
            if kind == "submission":
                rec["submissions"].append(ev)
            else:
                rec[kind] = ev
    return out


def _record(ws, ask_id):
    rec = _by_id(ws).get(ask_id)
    if not rec or not rec["compiled"]:
        raise LedgerError("ask.not_compiled", ask_id)
    return rec


def _append_delivery(ws, ask_id, compiled, mode, mechanism, state, receipt, limitations, actor=None):
    if _by_id(ws)[ask_id]["delivery"] is not None:
        raise LedgerError("delivery.duplicate", ask_id)
    cap = profiles.capability(profiles.for_host(compiled["data"]["host"]), compiled["data"]["selected_capability"]) or {}
    data = {"mode": mode, "mechanism": mechanism, "state": state, "qualification": cap.get("qualification", {"id": None}),
            "receipt": receipt, "submission": "unobserved" if mode == "human_handoff" else "not_applicable",
            "limitations": ["native acceptance does not prove instruction following, execution, or completion"] + list(limitations)}
    ev = _event("ask.delivery", ask_id, _actor(actor), data)
    schema.validate_event(ev)
    store.append(ws, ev)
    return {"ask_id": ask_id, **data}


def delivery_from_hook(ws, payload: dict) -> dict | None:
    """Record native_accepted (or delivery_failed) from a PostToolUse payload; never raise."""
    session = payload.get("session_id")
    host = "claude-code"
    if payload.get("hook_event_name") != "PostToolUse" or not session:
        return None
    tool = payload.get("tool_name")
    cutoff = datetime.now(timezone.utc) - HOOK_WINDOW
    candidates = []
    for ask_id, rec in _by_id(ws).items():
        c = rec["compiled"]
        if not c or rec["delivery"] or rec["cancelled"] or c["data"]["delivery_mode"] != "native_dispatch":
            continue
        if c["data"]["host"].get("session_ref") != session:
            continue
        cap = profiles.capability(profiles.for_host(c["data"]["host"]), c["data"]["selected_capability"]) or {}
        if (cap.get("activation") or {}).get("tool") != tool:
            continue
        if datetime.fromisoformat(c["time"].replace("Z", "+00:00")) < cutoff:
            continue
        candidates.append((ask_id, c))
    if len(candidates) != 1:
        sessions.log(ws, host, session, "delivery-skipped.jsonl",
                     {"reason": "ambiguous" if candidates else "no_candidate", "tool": tool, "candidates": [a for a, _ in candidates]})
        return None
    ask_id, compiled = candidates[0]
    response = payload.get("tool_response")
    failed = isinstance(response, dict) and (response.get("error") or response.get("is_error"))
    receipt = {"tool": tool, "tool_use_id": payload.get("tool_use_id"), "session_id": session,
               "response_sha256": digest.sha256_bytes(store.canonical(response)),
               "captured_by": "hook:PostToolUse"}
    return _append_delivery(ws, ask_id, compiled, "native_dispatch", "capability_activate",
                            "delivery_failed" if failed else "native_accepted", receipt,
                            [f"tool error: {response.get('error')}"] if failed else [])


def delivery_handoff(ws, ask_id: str) -> tuple[str, dict]:
    compiled = _record(ws, ask_id)["compiled"]
    path = ws.rf_dir / compiled["data"]["prompt"]["path"]
    host = compiled["data"]["host"]["name"]
    text = HANDOFF.format(host=host, capability=compiled["data"]["selected_capability"], path=path,
                          host_title=HOST_TITLES.get(host, host))
    rec = _append_delivery(ws, ask_id, compiled, "human_handoff", None, "handoff_ready",
                           {"path": compiled["data"]["prompt"]["path"], "emitted_by": "cli"}, ["submission unobserved"])
    return text, rec


def delivery_state(ws, ask_id: str, state: str, reason: str) -> dict:
    compiled = _record(ws, ask_id)["compiled"]
    mode = compiled["data"]["delivery_mode"] if compiled["data"]["delivery_mode"] != "unsupported" else "human_handoff"
    return _append_delivery(ws, ask_id, compiled, mode, None, state, None, [reason])


def submission_grade(rec) -> str:
    states = [s["data"]["state"] for s in rec["submissions"]]
    return "observed" if "observed" in states else "attributed" if "attributed" in states else "unobserved"


def _summary(ws, ask_id, rec):
    ev = rec["compiled"]
    d = ev["data"]
    outcome = "cancelled" if rec["cancelled"] else "confirmed" if rec["confirmed"] else "compiled"
    return {"id": ask_id, "ask_id": ask_id, "title": d["title"], "time": ev["time"], "outcome": outcome,
            "capability": d["selected_capability"], "session_ref": d["host"].get("session_ref"),
            "source_verified": d["source_verified"], "source": d["source"], "prompt": d["prompt"],
            "prompt_path": str(ws.rf_dir / d["prompt"]["path"]),
            "delivery": rec["delivery"]["data"]["state"] if rec["delivery"] else None,
            "submission": submission_grade(rec)}


def resolve(ws, session=None, kind="ask", reference=None) -> dict:
    """Ordered resolution; never picks the newest for being newest."""
    recs = {k: v for k, v in _by_id(ws).items() if v["compiled"]}
    summaries = [_summary(ws, k, v) for k, v in recs.items()]
    if reference:
        exact = [s for s in summaries if s["ask_id"] == reference]
        if exact:
            return {"candidates": exact, "rule_applied": "explicit_id"}
        hits = [s for s in summaries if reference.lower() in s["title"].lower()]
        if len(hits) == 1:
            return {"candidates": hits, "rule_applied": "explicit_title"}
        return {"candidates": hits or summaries, "rule_applied": "chooser"}
    if session:
        same = [s for s in summaries if s["session_ref"] == session]
        if same:
            return {"candidates": same, "rule_applied": "same_session"}
    return {"candidates": summaries, "rule_applied": "unique_in_workspace" if len(summaries) == 1 else "chooser"}


def show(ws, ask_id=None, session=None) -> dict:
    res = resolve(ws, session=session, reference=ask_id)
    if len(res["candidates"]) != 1:
        raise NeedsInput("no_record" if not res["candidates"] else "chooser", res["candidates"])
    return res["candidates"][0]
