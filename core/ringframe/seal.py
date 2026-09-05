"""Seal: bind a fresh Eval and unchanged subject to one authorized disposition. Fails closed."""

import json
from datetime import datetime, timezone

from ringframe import digest, evaluate, ids, schema, sessions, store
from ringframe.store import LedgerError
from ringframe.workspace import Workspace

DISPOSITIONS = ("accepted", "rejected", "deferred", "abandoned")
LIMITATIONS = ["a Seal is a decision record; it does not merge, publish, deploy, or certify correctness"]


class Refused(Exception):
    def __init__(self, codes: list[str]):
        super().__init__(", ".join(codes))
        self.codes = codes


def _now():
    return datetime.now(timezone.utc)


def _parse(t: str) -> datetime:
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def _authority(ws, actor, disposition, record) -> tuple[str | None, str | None]:
    """Return (authority string, refusal code)."""
    if actor["kind"] == "human" and actor.get("authority", "interactive") == "interactive":
        return "interactive", None
    path = ws.rf_dir / "authorizations" / f"{actor['id']}.json"
    if not path.exists():
        return None, "seal.authority_missing"
    grant = json.loads(path.read_text())
    allowed = grant.get("allowed", {})
    ok = (grant.get("actor") == f"{actor['kind']}:{actor['id']}"
          and disposition in allowed.get("dispositions", [])
          and record["verdict"] in allowed.get("eval_verdicts", [])
          and record["subject"]["kind"] in allowed.get("subject_kinds", [])
          and (not grant.get("expires") or _parse(grant["expires"]) > _now()))
    return (f"preauthorized:authorizations/{actor['id']}.json", None) if ok else (None, "seal.authority_missing")


def create(ws: Workspace, eval_id: str, disposition: str, acknowledge: list[str] | None = None, actor: dict | None = None) -> dict:
    if disposition not in DISPOSITIONS:
        raise LedgerError("seal.disposition", f"{disposition!r} not in {DISPOSITIONS}")
    actor = actor or {"kind": "human", "id": "local-user", "authority": "interactive"}
    acknowledge = list(acknowledge or [])
    codes = []
    record = evaluate.load_record(ws, eval_id)
    subject = {"kind": None, "ref": None}
    authority = None
    freshness = {}
    if record is None or not any(e["type"] == "eval.completed" and e["id"] == eval_id for e in store.events(ws)):
        codes.append("seal.eval_missing")
    else:
        subject = {"kind": record["subject"]["kind"], "ref": record["subject"]["ref"]}
        try:
            now_digest = evaluate.subject_digest(ws, subject["kind"], subject["ref"])
        except (LedgerError, OSError, __import__("subprocess").CalledProcessError):
            now_digest = None
        if now_digest != record["subject"]["sha256_after"]:
            codes.append("seal.subject_changed")
        max_age = evaluate.parse_iso_duration(record.get("freshness", {}).get("max_age", "PT24H"))
        age = (_now() - _parse(record["time"])).total_seconds()
        freshness = {"eval_time": record["time"], "max_age": record.get("freshness", {}).get("max_age", "PT24H"), "age_s": int(age)}
        if age > max_age:
            codes.append("seal.stale")
        authority, code = _authority(ws, actor, disposition, record)
        if code:
            codes.append(code)
        if disposition == "accepted" and record["verdict"] != "aligned" and not acknowledge:
            codes.append("seal.verdict_conflict")
        if any(e["type"] == "seal.created" and e["data"]["eval_id"] == eval_id and e["data"]["disposition"] == disposition
               for e in store.events(ws)):
            codes.append("seal.duplicate")
    seal_id = ids.new_id("sel")
    base = {"eval_id": eval_id, "subject": subject, "disposition": disposition,
            "authority": {**actor, "authority": authority or actor.get("authority")}, "freshness": freshness}
    if codes:
        ev = {"schema": store.SCHEMA, "event_id": ids.new_id("evt"), "type": "seal.refused", "time": sessions.now(), "id": seal_id,
              "actor": actor, "links": [{"rel": "seals", "id": eval_id}] if record else [], "data": {**base, "refusal_codes": codes}}
        schema.validate_event(ev)
        store.append(ws, ev)
        raise Refused(codes)
    receipt = {"schema": "ringframe.seal/1", "seal_id": seal_id,
               "eval": {"id": eval_id, "sha256": digest.sha256_file(ws.rf_dir / f"evals/{eval_id}.json"), "verdict": record["verdict"]},
               "subject": {**subject, "sha256": record["subject"]["sha256_after"]}, "disposition": disposition,
               "acknowledged": acknowledge, "actor": {**actor, "authority": authority},
               "limitations": list(record.get("limitations", [])) + LIMITATIONS, "time": sessions.now()}
    ref = store.publish(ws, f"seals/{seal_id}.json", store.canonical(receipt) + b"\n", role="seal_receipt")
    ev = {"schema": store.SCHEMA, "event_id": ids.new_id("evt"), "type": "seal.created", "time": receipt["time"], "id": seal_id,
          "actor": actor, "links": [{"rel": "seals", "id": eval_id}], "data": {**base, "artifact": ref}}
    schema.validate_event(ev)
    store.append(ws, ev)
    return receipt


def check(ws: Workspace, seal_id: str) -> dict:
    """Re-verify receipt, Eval, and subject digests now. Exit-code-free; the CLI maps `fresh`."""
    codes = []
    p = ws.rf_dir / f"seals/{seal_id}.json"
    created = next((e for e in store.events(ws) if e["type"] == "seal.created" and e["id"] == seal_id), None)
    if not p.exists() or created is None:
        return {"seal_id": seal_id, "fresh": False, "codes": ["seal.receipt_missing"]}
    if digest.sha256_file(p) != created["data"]["artifact"]["sha256"]:
        codes.append("seal.receipt_tampered")
    receipt = json.loads(p.read_bytes())
    eval_path = ws.rf_dir / f"evals/{receipt['eval']['id']}.json"
    if not eval_path.exists() or digest.sha256_file(eval_path) != receipt["eval"]["sha256"]:
        codes.append("seal.eval_changed")
    try:
        now_digest = evaluate.subject_digest(ws, receipt["subject"]["kind"], receipt["subject"]["ref"])
    except (LedgerError, OSError, __import__("subprocess").CalledProcessError):
        now_digest = None
    if now_digest != receipt["subject"]["sha256"]:
        codes.append("seal.subject_changed")
    return {"seal_id": seal_id, "fresh": not codes, "codes": codes, "disposition": receipt["disposition"], "verdict": receipt["eval"]["verdict"]}
