"""Atomic artifact publish, locked append-only ledger, and verification."""

import fcntl
import json
import os
import time
from pathlib import Path

from ringframe import digest
from ringframe.workspace import Workspace

SCHEMA = "ringframe.ledger/1"
LOCK_TIMEOUT_S = 10.0


class LedgerError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(ws: Workspace, rel_path: str, data: bytes, role: str) -> dict:
    """Write bytes to tmp, fsync, rename into place; final paths are never rewritten."""
    ws.ensure()
    final = ws.rf_dir / rel_path
    if final.exists():
        raise LedgerError("ledger.immutable", rel_path)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = ws.rf_dir / "tmp" / f"{rel_path.replace('/', '.')}.{os.getpid()}.{os.urandom(4).hex()}"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, final)
    _fsync_dir(final.parent)
    return digest.artifact_ref(role, rel_path, final)


def _acquire(lock_path: Path):
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + LOCK_TIMEOUT_S
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            if time.monotonic() > deadline:
                os.close(fd)
                raise LedgerError("ledger.lock_timeout", str(lock_path))
            time.sleep(0.005)


def append(ws: Workspace, event: dict) -> None:
    ws.ensure()
    line = canonical(event) + b"\n"
    ledger = ws.rf_dir / "ledger.jsonl"
    fd = _acquire(ws.rf_dir / "lock")
    try:
        if ledger.exists() and ledger.stat().st_size:
            with open(ledger, "rb") as f:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    raise LedgerError("ledger.torn_tail", "last line has no newline")
        out = os.open(ledger, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(out, line)
            os.fsync(out)
        finally:
            os.close(out)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def events(ws: Workspace) -> list[dict]:
    ledger = ws.rf_dir / "ledger.jsonl"
    if not ledger.exists():
        return []
    out = []
    with open(ledger, "rb") as f:
        for raw in f:
            if raw.strip():
                out.append(json.loads(raw))
    return out


def _refs(obj):
    if isinstance(obj, dict):
        if {"role", "path", "bytes", "sha256"} <= obj.keys():
            yield obj
        for v in obj.values():
            yield from _refs(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _refs(v)


def verify(ws: Workspace) -> list[dict]:
    """Stream the ledger; report findings without repairing anything."""
    findings = []
    ledger = ws.rf_dir / "ledger.jsonl"
    referenced, ids, links, deliveries, confirmed = set(), set(), [], {}, set()
    if ledger.exists():
        raw = ledger.read_bytes()
        if raw and not raw.endswith(b"\n"):
            findings.append({"code": "ledger.torn_tail"})
        for n, line in enumerate(raw.split(b"\n"), 1):
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                findings.append({"code": "ledger.invalid_json", "line": n})
                continue
            if ev.get("schema") != SCHEMA:
                findings.append({"code": "ledger.schema", "line": n, "path": "schema"})
            ids.add(ev.get("id"))
            links += [(n, l.get("id")) for l in ev.get("links", [])]
            t = ev.get("type")
            if t == "ask.confirmed":
                confirmed.add(ev.get("id"))
            if t == "ask.delivery":
                deliveries[ev.get("id")] = deliveries.get(ev.get("id"), 0) + 1
            for ref in _refs(ev.get("data", {})):
                referenced.add(ref["path"])
                p = ws.rf_dir / ref["path"]
                if not p.exists():
                    findings.append({"code": "artifact.missing", "line": n, "path": ref["path"]})
                elif p.stat().st_size != ref["bytes"] or digest.sha256_file(p) != ref["sha256"]:
                    findings.append({"code": "artifact.digest_mismatch", "line": n, "path": ref["path"]})
    for n, target in links:
        if target not in ids:
            findings.append({"code": "links.dangling", "line": n, "id": target})
    for ask_id, count in deliveries.items():
        if count > 1:
            findings.append({"code": "delivery.duplicate", "id": ask_id})
        if ask_id not in confirmed:
            findings.append({"code": "delivery.without_confirmation", "id": ask_id})
    for sub in ("asks", "evals", "seals"):
        base = ws.rf_dir / sub
        if base.exists():
            for p in base.rglob("*"):
                if p.is_file() and p.relative_to(ws.rf_dir).as_posix() not in referenced:
                    findings.append({"code": "artifact.unreferenced", "path": p.relative_to(ws.rf_dir).as_posix()})
    return findings
