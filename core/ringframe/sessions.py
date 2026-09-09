"""Bounded, prunable hook captures under .fab7/rf/sessions/<host>/<session>/."""

import json
import re
import shutil
import time
from datetime import datetime, timezone

from ringframe import digest
from ringframe.store import canonical
from ringframe.workspace import Workspace

PREFIXES = ("/rf:", "$rf:")  # Claude Code slash skill, Codex dollar skill


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _dir(ws: Workspace, host: str, session: str):
    ws.ensure()
    d = ws.rf_dir / "sessions" / host / session
    d.mkdir(parents=True, exist_ok=True)
    return d


def log(ws: Workspace, host: str, session: str, name: str, record: dict) -> None:
    with open(_dir(ws, host, session) / name, "ab") as f:
        f.write(canonical({"time": now(), **record}) + b"\n")


def capture(ws: Workspace, host: str, payload: dict, host_version: str | None = None) -> dict | None:
    """Store a `/rf:` or `$rf:` invocation in full; every other prompt as digest and byte count only (never its text)."""
    prompt = payload.get("prompt")
    session = payload.get("session_id")
    if not isinstance(prompt, str) or not prompt or not session:
        return None
    data = prompt.encode("utf-8")
    rec = {"session_id": session, "sha256": digest.sha256_bytes(data), "bytes": len(data), "cwd": payload.get("cwd"),
           "permission_mode": payload.get("permission_mode"), "host_version": (host_version or "").strip() or None}
    if prompt.startswith(PREFIXES):
        rec["prompt"] = prompt
    log(ws, host, session, "prompts.jsonl", rec)
    return rec


def source_verified(ws: Workspace, host: str, session: str | None, source: bytes) -> tuple[str, str | None]:
    """Compare source bytes with the argument bytes of a captured `/rf:ask` invocation."""
    if not session:
        return "unverified", "no_session_ref"
    path = ws.rf_dir / "sessions" / host / session / "prompts.jsonl"
    if not path.exists():
        return "unverified", "no_capture"
    want = source.decode("utf-8", "surrogateescape").removesuffix("\n")
    for line in path.read_bytes().splitlines():
        if _matches(json.loads(line).get("prompt", ""), want):
            return "exact", None
    return "unverified", "mismatch"


def _matches(prompt: str, want: str) -> bool:
    head, _, args = prompt.partition(" ")
    return head in {p + "ask" for p in PREFIXES} and args.removesuffix("\n") == want


def resolve_session(ws: Workspace, host: str, source: bytes, window_s: int = 1800) -> dict | None:
    """The one session whose recent captured `/rf:ask` invocation carries exactly these source bytes.

    The model never knows its own session id; the hook does. Ambiguity resolves to None."""
    base = ws.rf_dir / "sessions" / host
    want = source.decode("utf-8", "surrogateescape").removesuffix("\n")
    cutoff = time.time() - window_s
    hits = []
    for path in sorted(base.glob("*/prompts.jsonl")) if base.exists() else []:
        if path.stat().st_mtime < cutoff:
            continue
        for line in path.read_bytes().splitlines():
            rec = json.loads(line)
            if _matches(rec.get("prompt", ""), want):
                hits.append({"session_ref": path.parent.name, "host_version": rec.get("host_version")})
                break
    return hits[0] if len(hits) == 1 else None


def parse_duration(text: str) -> int:
    m = re.fullmatch(r"(\d+)([dh])", text)
    if not m:
        raise ValueError("duration must look like 7d or 36h")
    return int(m.group(1)) * (86400 if m.group(2) == "d" else 3600)


def prune(ws: Workspace, older_than: str) -> list[str]:
    cutoff = time.time() - parse_duration(older_than)
    removed = []
    base = ws.rf_dir / "sessions"
    for host_dir in sorted(base.iterdir()) if base.exists() else []:
        for sess in sorted(host_dir.iterdir()):
            newest = max((p.stat().st_mtime for p in sess.iterdir()), default=sess.stat().st_mtime)
            if newest < cutoff:
                shutil.rmtree(sess)
                removed.append(f"{host_dir.name}/{sess.name}")
    return removed
