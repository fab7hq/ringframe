import pytest

from ringframe import schema
from ringframe.store import LedgerError

BASE = {"schema": "ringframe.ledger/1", "event_id": "evt_1", "type": "ask.cancelled", "time": "2026-01-01T00:00:00.000Z",
        "id": "ask_1", "actor": {"kind": "human", "id": "u", "authority": "interactive"}, "links": []}
REF = {"role": "source_intent", "path": "asks/ask_1/source.txt", "bytes": 1, "sha256": "a" * 64}


def cancelled():
    return {**BASE, "data": {"title": "t", "classification": {"task": ["plan"], "result": "plan", "interaction": "interactive",
                                                                "horizon": "session", "effects": ["read"]},
                             "selected_capability": "native_plan", "route_explanation": {"fits": "x", "alternatives": [], "continuation": "c", "effects": "e", "gaps": []},
                             "host": {"name": "claude-code", "version": "2.1.260", "surface": "native-tui", "session_ref": None,
                                      "workspace": {"root": "/w", "rule": "cwd"}, "profile_id": "claude-code@2.1", "profile_sha256": "b" * 64},
                             "source": REF, "prompt": {**REF, "role": "generated_prompt", "path": "asks/ask_1/prompt.txt"},
                             "source_verified": "unverified", "limitations": []}}


def test_valid_event_passes():
    schema.validate_event(cancelled())


def test_missing_required_key_reports_path():
    ev = cancelled()
    del ev["data"]["prompt"]
    with pytest.raises(LedgerError) as e:
        schema.validate_event(ev)
    assert e.value.code == "ledger.schema" and "data.prompt" in e.value.detail


def test_unknown_top_level_key_rejected():
    with pytest.raises(LedgerError, match="extra"):
        schema.validate_event({**cancelled(), "extra": 1})


def test_bad_enum_rejected():
    ev = cancelled()
    ev["data"]["classification"]["result"] = "poem"
    with pytest.raises(LedgerError, match="classification.result"):
        schema.validate_event(ev)


def test_delivery_requires_mode_state_and_qualification():
    ev = {**BASE, "type": "ask.delivery", "data": {"mode": "human_handoff", "mechanism": None, "state": "handoff_ready",
                                                   "qualification": {"id": None}, "receipt": {"path": "asks/ask_1/prompt.txt", "emitted_by": "cli"},
                                                   "submission": "unobserved", "limitations": []}}
    schema.validate_event(ev)
    ev["data"]["state"] = "sent"
    with pytest.raises(LedgerError, match="data.state"):
        schema.validate_event(ev)


def test_every_event_type_has_a_required_key_list():
    assert set(schema.REQUIRED) == {"ask.confirmed", "ask.cancelled", "ask.delivery", "eval.completed", "seal.created", "seal.refused"}
