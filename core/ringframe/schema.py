"""Event validation: required keys, enums, and no unknown top-level keys."""

from ringframe.store import LedgerError, SCHEMA

TOP = {"schema", "event_id", "type", "time", "id", "actor", "links", "data"}
ENUMS = {
    "actor.kind": {"human", "agent", "policy"},
    "links[].rel": {"revises", "remediates", "evaluates", "seals", "supersedes"},
    "classification.task[]": {"question", "research", "clarify", "plan", "implement", "diagnose", "review", "operate", "document"},
    "classification.result": {"answer", "plan", "workspace_change", "evidence", "continuing_objective"},
    "classification.interaction": {"interactive", "approval_gated"},
    "classification.horizon": {"one_turn", "session", "persistent"},
    "classification.effects[]": {"read", "write", "execute", "external_effect", "workspace_read", "workspace_write", "external_read"},
    "data.delivery_mode": {"native_dispatch", "human_handoff", "unsupported"},
    "data.source_verified": {"exact", "unverified"},
    "data.mode": {"native_dispatch", "human_handoff"},
    "data.mechanism": {"capability_activate", "prompt_submit", None},
    "data.state": {"native_accepted", "handoff_ready", "delivery_failed", "unavailable"},
    "data.submission": {"unobserved", "not_applicable"},
    "submission.state": {"observed", "attributed"},
    "data.verdict": {"aligned", "drifted", "incomplete"},
    "data.disposition": {"accepted", "rejected", "deferred", "abandoned"},
}
ASK_COMMON = ["title", "classification", "selected_capability", "route_explanation", "host", "source", "prompt", "source_verified", "limitations"]
REQUIRED = {
    "ask.compiled": ASK_COMMON + ["delivery_mode"],
    "ask.confirmed": ["confirmation"],
    "ask.cancelled": ["cancellation"],
    "ask.submission": ["state", "observed_by", "attributed_by", "as_modified", "host", "prompt_sha256"],
    "ask.delivery": ["mode", "mechanism", "state", "qualification", "receipt", "submission", "limitations"],
    "eval.opened": ["brief", "basis", "anchor", "subject"],
    "eval.completed": ["basis", "subject", "verdict", "confidence", "artifact", "limitations"],
    "seal.created": ["basis", "eval", "subject", "disposition", "authority", "artifact"],
    "seal.refused": ["basis", "eval", "subject", "disposition", "authority", "refusal_codes"],
}
REF_KEYS = {"role", "path", "bytes", "sha256"}


def _fail(path, why="missing"):
    raise LedgerError("ledger.schema", f"{path} {why}")


def _enum(path, key, value):
    allowed = sorted(v for v in ENUMS[key] if v is not None)
    if not isinstance(value, (str, type(None))):
        _fail(path, f"must be one of {allowed}, got {type(value).__name__}")
    if value not in ENUMS[key]:
        _fail(path, f"must be one of {allowed}, got {value!r}")


def _enum_list(path, key, values):
    if not isinstance(values, list):
        _fail(path, f"must be a list from {sorted(ENUMS[key])}, got {type(values).__name__}")
    for v in values:
        _enum(f"{path}[]", key, v)


def _ref(path, ref):
    if not isinstance(ref, dict) or not REF_KEYS <= ref.keys():
        _fail(path, "is not an artifact reference")


def validate_event(ev: dict) -> None:
    extra = set(ev) - TOP
    if extra:
        _fail(",".join(sorted(extra)), "extra top-level key")
    for k in TOP:
        if k not in ev:
            _fail(k)
    if ev["schema"] != SCHEMA:
        _fail("schema", f"must be {SCHEMA}")
    if ev["type"] not in REQUIRED:
        _fail("type", "unknown event type")
    for k in ("kind", "id"):
        if k not in ev["actor"]:
            _fail(f"actor.{k}")
    _enum("actor.kind", "actor.kind", ev["actor"]["kind"])
    for i, link in enumerate(ev["links"]):
        if "rel" not in link or "id" not in link:
            _fail(f"links[{i}]")
        _enum(f"links[{i}].rel", "links[].rel", link["rel"])
    data = ev["data"]
    for k in REQUIRED[ev["type"]]:
        if k not in data:
            _fail(f"data.{k}")
    if ev["type"] == "ask.compiled":
        c = data["classification"]
        for k in ("task", "result", "interaction", "horizon", "effects"):
            if k not in c:
                _fail(f"data.classification.{k}")
        _enum_list("data.classification.task", "classification.task[]", c["task"])
        for k in ("result", "interaction", "horizon"):
            _enum(f"data.classification.{k}", f"classification.{k}", c[k])
        _enum_list("data.classification.effects", "classification.effects[]", c["effects"])
        if "concerns" in c and not (isinstance(c["concerns"], list) and all(isinstance(x, str) for x in c["concerns"])):
            _fail("data.classification.concerns", "must be a list of strings from the domain vocabulary")
        comp = data.get("compiler")
        if comp is not None and (not isinstance(comp, dict) or comp.get("source") not in ("prompt", "body", "composed")):
            _fail("data.compiler", "must be {source: prompt|body|composed, ...}")
        for k in ("name", "version", "surface", "session_ref", "workspace", "profile_id", "profile_sha256"):
            if k not in data["host"]:
                _fail(f"data.host.{k}")
        _ref("data.source", data["source"])
        _ref("data.prompt", data["prompt"])
        _enum("data.source_verified", "data.source_verified", data["source_verified"])
        _enum("data.delivery_mode", "data.delivery_mode", data["delivery_mode"])
    elif ev["type"] in ("ask.confirmed", "ask.cancelled"):
        grade = data["confirmation" if ev["type"] == "ask.confirmed" else "cancellation"]
        if not isinstance(grade, dict) or not ({"observed_by", "attributed_by"} & grade.keys()):
            _fail(f"data.{'confirmation' if ev['type'] == 'ask.confirmed' else 'cancellation'}", "needs observed_by or attributed_by")
    elif ev["type"] == "ask.submission":
        _enum("data.state", "submission.state", data["state"])
        if not (data["observed_by"] or data["attributed_by"]):
            _fail("data.observed_by", "or attributed_by is required")
    elif ev["type"] == "ask.delivery":
        for k in ("mode", "mechanism", "state", "submission"):
            _enum(f"data.{k}", f"data.{k}", data[k])
        if "id" not in data["qualification"]:
            _fail("data.qualification.id")
    elif ev["type"] == "eval.opened":
        _ref("data.brief", data["brief"])
    elif ev["type"] == "eval.completed":
        _enum("data.verdict", "data.verdict", data["verdict"])
        if not isinstance(data["confidence"], (int, float)) or not 0 <= data["confidence"] <= 1:
            _fail("data.confidence", "must be a number in [0, 1]")
        _ref("data.artifact", data["artifact"])
    else:
        _enum("data.disposition", "data.disposition", data["disposition"])
        if ev["type"] == "seal.created":
            _ref("data.artifact", data["artifact"])
