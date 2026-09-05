import json
import multiprocessing
import os
import sys

import pytest

from ringframe import store, workspace
from ringframe.store import LedgerError


def ws_for(path):
    ws = workspace.resolve(cwd=path)
    ws.ensure()
    return ws


def test_publish_is_atomic_and_immutable(repo):
    ws = ws_for(repo)
    ref = store.publish(ws, "asks/ask_x/source.txt", b"intent\n", role="source_intent")
    assert (ws.rf_dir / "asks/ask_x/source.txt").read_bytes() == b"intent\n"
    assert ref["bytes"] == 7 and ref["role"] == "source_intent"
    assert list((ws.rf_dir / "tmp").iterdir()) == []
    with pytest.raises(LedgerError, match="ledger.immutable"):
        store.publish(ws, "asks/ask_x/source.txt", b"other\n", role="source_intent")


def test_append_canonical_line_and_read_back(repo):
    ws = ws_for(repo)
    ev = {"schema": "ringframe.ledger/1", "event_id": "evt_1", "type": "x", "time": "t", "id": "i",
          "actor": {"kind": "human", "id": "u"}, "links": [], "data": {"b": 1, "a": "ü"}}
    store.append(ws, ev)
    raw = (ws.rf_dir / "ledger.jsonl").read_bytes()
    assert raw.endswith(b"\n") and raw.count(b"\n") == 1
    assert b'"data":{"a":"\xc3\xbc","b":1}' in raw
    assert store.events(ws) == [ev]


def test_torn_tail_refuses_append(repo):
    ws = ws_for(repo)
    (ws.rf_dir / "ledger.jsonl").write_bytes(b'{"partial": ')
    with pytest.raises(LedgerError, match="ledger.torn_tail"):
        store.append(ws, {"schema": "ringframe.ledger/1"})


def _worker(root, n):
    ws = workspace.resolve(cwd=root)
    for i in range(n):
        store.append(ws, {"schema": "ringframe.ledger/1", "event_id": f"evt_{os.getpid()}_{i}", "type": "t",
                          "time": "t", "id": "i", "actor": {"kind": "human", "id": "u"}, "links": [], "data": {}})


def test_concurrent_appends_never_tear(repo):
    ws = ws_for(repo)
    ctx = multiprocessing.get_context("spawn" if sys.platform == "darwin" else "fork")
    procs = [ctx.Process(target=_worker, args=(str(repo), 100)) for _ in range(10)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
        assert p.exitcode == 0
    lines = (ws.rf_dir / "ledger.jsonl").read_bytes().split(b"\n")
    assert lines[-1] == b"" and len(lines) == 1001
    assert len({json.loads(l)["event_id"] for l in lines[:-1]}) == 1000


def test_verify_reports_unreferenced_and_missing(repo):
    ws = ws_for(repo)
    store.publish(ws, "asks/ask_a/source.txt", b"x", role="source_intent")  # never referenced
    ref = store.publish(ws, "asks/ask_b/source.txt", b"y", role="source_intent")
    ref2 = store.publish(ws, "asks/ask_b/prompt.txt", b"z", role="generated_prompt")
    store.append(ws, {"schema": "ringframe.ledger/1", "event_id": "evt_1", "type": "ask.cancelled", "time": "t",
                      "id": "ask_b", "actor": {"kind": "human", "id": "u"}, "links": [],
                      "data": {"source": ref, "prompt": ref2}})
    (ws.rf_dir / "asks/ask_b/prompt.txt").unlink()
    codes = sorted(f["code"] for f in store.verify(ws))
    assert codes == ["artifact.missing", "artifact.unreferenced"]


def test_verify_detects_digest_mismatch_and_dangling_link(repo):
    ws = ws_for(repo)
    ref = store.publish(ws, "asks/ask_b/source.txt", b"y", role="source_intent")
    os.chmod(ws.rf_dir / "asks/ask_b/source.txt", 0o600)
    (ws.rf_dir / "asks/ask_b/source.txt").write_bytes(b"tampered")
    store.append(ws, {"schema": "ringframe.ledger/1", "event_id": "evt_1", "type": "ask.cancelled", "time": "t",
                      "id": "ask_b", "actor": {"kind": "human", "id": "u"},
                      "links": [{"rel": "revises", "id": "ask_nope"}], "data": {"source": ref}})
    codes = sorted(f["code"] for f in store.verify(ws))
    assert codes == ["artifact.digest_mismatch", "links.dangling"]
