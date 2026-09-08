"""Seal: the person's decision to close the open Asks. It records the latest Eval as a fact and gates nothing."""

import json
import subprocess
from datetime import datetime, timezone

from ringframe import ask, digest, evaluate, ids, schema, sessions, store
from ringframe.store import LedgerError
from ringframe.workspace import Workspace

DISPOSITIONS = ("accepted", "rejected", "deferred", "abandoned")
LIMITATIONS = ["a Seal is a decision record; it does not merge, publish, deploy, or certify correctness",
               "the Eval it records is a judgement with a confidence, not a gate"]


class Refused(Exception):
    def __init__(self, codes: list[str]):
        super().__init__(", ".join(codes))
        self.codes = codes


def _now():
    return datetime.now(timezone.utc)


def _parse(t: str) -> datetime:
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def _authority(ws, actor, disposition, subject_kind) -> tuple[str | None, str | None]:
    """Interactive humans decide by being present; any other actor needs a pre-authorization record."""
    if actor["kind"] == "human" and actor.get("authority", "interactive") == "interactive":
        return "interactive", None
    path = ws.rf_dir / "authorizations" / f"{actor['id']}.json"
    if not path.exists():
        return None, "seal.authority_missing"
    grant = json.loads(path.read_text())
    allowed = grant.get("allowed", {})
    ok = (grant.get("actor") == f"{actor['kind']}:{actor['id']}"
          and disposition in allowed.get("dispositions", [])
          and subject_kind in allowed.get("subject_kinds", [])
          and (not grant.get("expires") or _parse(grant["expires"]) > _now()))
    return (f"preauthorized:authorizations/{actor['id']}.json", None) if ok else (None, "seal.authority_missing")


def _eval_fact(ws, record, subject_sha) -> dict | None:
    if record is None:
        return None
    return {"eval_id": record["eval_id"], "verdict": record["verdict"], "confidence": record["confidence"],
            "sha256": digest.sha256_file(ws.rf_dir / f"evals/{record['eval_id']}/record.json"),
            "subject_matches": record["subject"]["sha256"] == subject_sha, "age_s": int((_now() - _parse(record["time"])).total_seconds())}


def create(ws: Workspace, disposition: str, *, eval_id: str | None = None, note: str | None = None, actor: dict | None = None) -> dict:
    if disposition not in DISPOSITIONS:
        raise LedgerError("seal.disposition", f"{disposition!r} not in {DISPOSITIONS}")
    actor = actor or {"kind": "human", "id": "local-user", "authority": "interactive"}
    codes = []
    asks = ask.open_asks(ws)
    ask_ids = [a["ask_id"] for a in asks]
    if not ask_ids:
        codes.append("seal.no_open_ask")
    try:
        kind, ref = evaluate.default_subject(ws)
        subject = {"kind": kind, "ref": ref, "sha256": evaluate.subject_digest(ws, kind, ref)}
    except (subprocess.CalledProcessError, FileNotFoundError, LedgerError):  # not a Git repository: the receipt still records the decision
        subject = {"kind": None, "ref": None, "sha256": None}
    record = evaluate.load_record(ws, eval_id) if eval_id else evaluate.latest_for(ws, ask_ids)
    if eval_id and record is None:
        codes.append("seal.eval_missing")
    elif eval_id and not set(record["basis"]["asks"]) & set(ask_ids):
        codes.append("seal.eval_unrelated")
        record = None
    authority, code = _authority(ws, actor, disposition, subject["kind"])
    if code:
        codes.append(code)
    seal_id = ids.new_id("sel")
    fact = _eval_fact(ws, record, subject["sha256"])
    base = {"basis": {"asks": ask_ids}, "eval": fact, "subject": subject, "disposition": disposition,
            "authority": {**actor, "authority": authority or actor.get("authority")}, **({"note": note} if note else {})}
    links = [{"rel": "seals", "id": a} for a in ask_ids] + ([{"rel": "seals", "id": record["eval_id"]}] if record else [])
    if codes:
        ev = {"schema": store.SCHEMA, "event_id": ids.new_id("evt"), "type": "seal.refused", "time": sessions.now(), "id": seal_id,
              "actor": actor, "links": links, "data": {**base, "refusal_codes": codes}}
        schema.validate_event(ev)
        store.append(ws, ev)
        raise Refused(codes)
    limitations = list(LIMITATIONS)
    if fact is None:
        limitations.append("no Eval over these Asks; the decision rests on the person alone")
    elif not fact["subject_matches"]:
        limitations.append("the subject changed after the Eval; its verdict describes an earlier state")
    receipt = {"schema": "ringframe.seal/1", "seal_id": seal_id, **base, "asks": [{"ask_id": a["ask_id"], "title": a["title"]} for a in asks],
               "limitations": limitations, "time": sessions.now()}
    ref_ = store.publish(ws, f"seals/{seal_id}.json", store.canonical(receipt) + b"\n", role="seal_receipt")
    ev = {"schema": store.SCHEMA, "event_id": ids.new_id("evt"), "type": "seal.created", "time": receipt["time"], "id": seal_id,
          "actor": actor, "links": links, "data": {**base, "artifact": ref_}}
    schema.validate_event(ev)
    store.append(ws, ev)
    return receipt


def check(ws: Workspace, seal_id: str) -> dict:
    """Re-verify the receipt and its Eval record now, and say whether the subject still matches. It decides nothing."""
    codes = []
    p = ws.rf_dir / f"seals/{seal_id}.json"
    created = next((e for e in store.events(ws) if e["type"] == "seal.created" and e["id"] == seal_id), None)
    if not p.exists() or created is None:
        return {"seal_id": seal_id, "fresh": False, "codes": ["seal.receipt_missing"]}
    if digest.sha256_file(p) != created["data"]["artifact"]["sha256"]:
        codes.append("seal.receipt_tampered")
    receipt = json.loads(p.read_bytes())
    fact = receipt["eval"]
    if fact:
        eval_path = ws.rf_dir / f"evals/{fact['eval_id']}/record.json"
        if not eval_path.exists() or digest.sha256_file(eval_path) != fact["sha256"]:
            codes.append("seal.eval_changed")
    subject = receipt["subject"]
    try:
        now_digest = evaluate.subject_digest(ws, subject["kind"], subject["ref"]) if subject["kind"] else None
    except (subprocess.CalledProcessError, FileNotFoundError, LedgerError):
        now_digest = None
    return {"seal_id": seal_id, "fresh": not codes, "codes": codes, "disposition": receipt["disposition"], "basis": receipt["basis"],
            "eval": {"eval_id": fact["eval_id"], "verdict": fact["verdict"], "confidence": fact["confidence"]} if fact else None,
            "subject_matches": now_digest is not None and now_digest == subject["sha256"]}
