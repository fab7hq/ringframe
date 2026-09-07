import pytest

from ringframe import schema
from ringframe.store import LedgerError

BASE = {"schema": "ringframe.ledger/1", "event_id": "evt_1", "type": "ask.compiled", "time": "2026-01-01T00:00:00.000Z",
        "id": "ask_1", "actor": {"kind": "human", "id": "u", "authority": "interactive"}, "links": []}
REF = {"role": "source_intent", "path": "asks/ask_1/source.txt", "bytes": 1, "sha256": "a" * 64}


def cancelled():
    return {**BASE, "data": {"delivery_mode": "native_dispatch", "title": "t", "classification": {"task": ["plan"], "result": "plan", "interaction": "interactive",
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
    assert set(schema.REQUIRED) == {"ask.compiled", "ask.confirmed", "ask.cancelled", "ask.submission", "ask.delivery", "eval.opened", "eval.completed", "seal.created", "seal.refused"}


def test_confirmed_cancelled_and_submission_are_graded_observations():
    schema.validate_event({**BASE, "type": "ask.confirmed", "data": {"confirmation": {"observed_by": "skill", "surface": "AskUserQuestion"}}})
    schema.validate_event({**BASE, "type": "ask.cancelled", "data": {"cancellation": {"attributed_by": "human:local-user"}, "reason": "later"}})
    schema.validate_event({**BASE, "type": "ask.submission", "data": {"state": "observed", "observed_by": "hook:UserPromptSubmit", "attributed_by": None,
                                                                       "as_modified": False, "host": {"name": "claude-code", "session_ref": "s"}, "prompt_sha256": "a" * 64}})
    with pytest.raises(LedgerError, match="data.state"):
        schema.validate_event({**BASE, "type": "ask.submission", "data": {"state": "probably", "observed_by": None, "attributed_by": "human:x", "as_modified": False, "host": {}, "prompt_sha256": "a" * 64}})
    with pytest.raises(LedgerError, match="data.confirmation"):
        schema.validate_event({**BASE, "type": "ask.confirmed", "data": {}})


@pytest.mark.parametrize("field,value,expect", [
    ("task", "implement", "task must be a list"),                 # string where a list belongs: never iterate its characters
    ("result", ["workspace_change"], "result must be one of"),   # list where a string belongs: never an internal TypeError
    ("effects", "write", "effects must be a list"),
    ("horizon", None, "horizon must be one of"),
])
def test_wrong_shapes_report_the_expected_shape_not_an_internal_error(field, value, expect):
    ev = cancelled()
    ev["data"]["classification"][field] = value
    with pytest.raises(LedgerError) as e:
        schema.validate_event(ev)
    assert e.value.code == "ledger.schema" and expect in e.value.detail
