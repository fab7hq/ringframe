"""Ask: persist one confirmed or cancelled intent, record observable delivery, resolve records."""

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


def _persist(ws, type_, staged, title, capability, classification, route, host, links, limitations, actor, extra):
    source, prompt = _staged(staged)
    profile = profiles.for_host(host)
    cap = profiles.capability(profile, capability)
    if cap is None:
        raise LedgerError("ask.capability", f"{capability!r} is not in profile {profile['profile_id']}")
    limitations = list(limitations or []) + list(cap.get("limitations", []))
    if profile["profile_id"] == "unknown":
        limitations.append("qualification gap: no profile for this host and version")
    ask_id = ids.new_id("ask")
    source_ref = store.publish(ws, f"asks/{ask_id}/source.txt", source, role="source_intent")
    prompt_ref = store.publish(ws, f"asks/{ask_id}/prompt.txt", prompt, role="generated_prompt")
    verified, reason = sessions.source_verified(ws, host["name"], host.get("session_ref"), source)
    if reason:
        limitations.append(f"source_verified unverified: {reason}")
    data = {"title": title, "classification": classification, "selected_capability": capability, "route_explanation": route,
            "host": {"name": host["name"], "version": host.get("version"), "surface": host.get("surface"),
                     "session_ref": host.get("session_ref"), "workspace": ws.describe(),
                     "profile_id": profile["profile_id"], "profile_sha256": profiles.sha256(profile["profile_id"].split("@")[0] if profile["host"] else "unknown")},
            "source": source_ref, "prompt": prompt_ref, "source_verified": verified, "limitations": limitations, **extra}
    if type_ == "ask.confirmed":
        data["delivery_mode"] = cap["delivery_mode"]
    ev = _event(type_, ask_id, _actor(actor), data, links)
    schema.validate_event(ev)
    store.append(ws, ev)
    shutil.rmtree(staged)
    return {"ask_id": ask_id, "source": source_ref, "prompt": prompt_ref, "prompt_path": str(ws.rf_dir / prompt_ref["path"]),
            "source_verified": verified, **({"delivery_mode": data["delivery_mode"]} if type_ == "ask.confirmed" else {})}


def confirm(ws, *, staged, title, capability, classification, route, host, links=(), limitations=(), actor=None):
    return _persist(ws, "ask.confirmed", staged, title, capability, classification, route, host, links, limitations, actor, {})


def cancel(ws, *, staged, title, capability, classification, route, host, links=(), limitations=(), actor=None, reason=None):
    extra = {"reason": reason} if reason else {}
    return _persist(ws, "ask.cancelled", staged, title, capability, classification, route, host, links, limitations, actor, extra)


def _by_id(ws) -> dict:
    """ask_id -> {"confirmed": event, "delivery": event|None, "cancelled": event|None}."""
    out = {}
    for ev in store.events(ws):
        if ev["type"].startswith("ask."):
            rec = out.setdefault(ev["id"], {"confirmed": None, "cancelled": None, "delivery": None})
            rec[ev["type"].split(".")[1]] = ev
    return out


def _append_delivery(ws, ask_id, confirmed, mode, mechanism, state, receipt, limitations, actor=None):
    if _by_id(ws)[ask_id]["delivery"] is not None:
        raise LedgerError("delivery.duplicate", ask_id)
    cap = profiles.capability(profiles.for_host(confirmed["data"]["host"]), confirmed["data"]["selected_capability"]) or {}
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
        c = rec["confirmed"]
        if not c or rec["delivery"] or c["data"]["delivery_mode"] != "native_dispatch":
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
    ask_id, confirmed = candidates[0]
    response = payload.get("tool_response")
    failed = isinstance(response, dict) and (response.get("error") or response.get("is_error"))
    receipt = {"tool": tool, "tool_use_id": payload.get("tool_use_id"), "session_id": session,
               "response_sha256": digest.sha256_bytes(store.canonical(response)),
               "captured_by": "hook:PostToolUse"}
    return _append_delivery(ws, ask_id, confirmed, "native_dispatch", "capability_activate",
                            "delivery_failed" if failed else "native_accepted", receipt,
                            [f"tool error: {response.get('error')}"] if failed else [])


def delivery_handoff(ws, ask_id: str) -> tuple[str, dict]:
    confirmed = _confirmed(ws, ask_id)
    path = ws.rf_dir / confirmed["data"]["prompt"]["path"]
    host = confirmed["data"]["host"]["name"]
    text = HANDOFF.format(host=host, capability=confirmed["data"]["selected_capability"], path=path,
                          host_title=HOST_TITLES.get(host, host))
    rec = _append_delivery(ws, ask_id, confirmed, "human_handoff", None, "handoff_ready",
                           {"path": confirmed["data"]["prompt"]["path"], "emitted_by": "cli"}, ["submission unobserved"])
    return text, rec


def delivery_state(ws, ask_id: str, state: str, reason: str) -> dict:
    confirmed = _confirmed(ws, ask_id)
    mode = confirmed["data"]["delivery_mode"] if confirmed["data"]["delivery_mode"] != "unsupported" else "human_handoff"
    return _append_delivery(ws, ask_id, confirmed, mode, None, state, None, [reason])


def _confirmed(ws, ask_id):
    rec = _by_id(ws).get(ask_id)
    if not rec or not rec["confirmed"]:
        raise LedgerError("ask.not_confirmed", ask_id)
    return rec["confirmed"]


def _summary(ws, ask_id, rec):
    ev = rec["confirmed"] or rec["cancelled"]
    d = ev["data"]
    return {"id": ask_id, "ask_id": ask_id, "title": d["title"], "time": ev["time"], "outcome": ev["type"].split(".")[1],
            "capability": d["selected_capability"], "session_ref": d["host"].get("session_ref"),
            "source_verified": d["source_verified"], "source": d["source"], "prompt": d["prompt"],
            "prompt_path": str(ws.rf_dir / d["prompt"]["path"]),
            "delivery": rec["delivery"]["data"]["state"] if rec["delivery"] else None}


def resolve(ws, session=None, kind="ask", reference=None) -> dict:
    """Ordered resolution; never picks the newest for being newest."""
    recs = {k: v for k, v in _by_id(ws).items() if v["confirmed"] or v["cancelled"]}
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
