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
    "data.verdict": {"aligned", "drifted", "incomplete"},
    "data.disposition": {"accepted", "rejected", "deferred", "abandoned"},
}
ASK_COMMON = ["title", "classification", "selected_capability", "route_explanation", "host", "source", "prompt", "source_verified", "limitations"]
REQUIRED = {
    "ask.confirmed": ASK_COMMON + ["delivery_mode"],
    "ask.cancelled": ASK_COMMON,
    "ask.delivery": ["mode", "mechanism", "state", "qualification", "receipt", "submission", "limitations"],
    "eval.completed": ["subject", "definition_sha256", "verdict", "counts", "forbidden_effects_observed", "artifact", "limitations"],
    "seal.created": ["eval_id", "subject", "disposition", "authority", "freshness", "artifact"],
    "seal.refused": ["eval_id", "subject", "disposition", "authority", "freshness", "refusal_codes"],
}
REF_KEYS = {"role", "path", "bytes", "sha256"}


def _fail(path, why="missing"):
    raise LedgerError("ledger.schema", f"{path} {why}")


def _enum(path, key, value):
    if value not in ENUMS[key]:
        _fail(path, f"not in {sorted(v for v in ENUMS[key] if v is not None)}")


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
    if ev["type"] in ("ask.confirmed", "ask.cancelled"):
        c = data["classification"]
        for k in ("task", "result", "interaction", "horizon", "effects"):
            if k not in c:
                _fail(f"data.classification.{k}")
        for t in c["task"]:
            _enum("data.classification.task[]", "classification.task[]", t)
        for k in ("result", "interaction", "horizon"):
            _enum(f"data.classification.{k}", f"classification.{k}", c[k])
        for e in c["effects"]:
            _enum("data.classification.effects[]", "classification.effects[]", e)
        for k in ("name", "version", "surface", "session_ref", "workspace", "profile_id", "profile_sha256"):
            if k not in data["host"]:
                _fail(f"data.host.{k}")
        _ref("data.source", data["source"])
        _ref("data.prompt", data["prompt"])
        _enum("data.source_verified", "data.source_verified", data["source_verified"])
        if ev["type"] == "ask.confirmed":
            _enum("data.delivery_mode", "data.delivery_mode", data["delivery_mode"])
    elif ev["type"] == "ask.delivery":
        for k in ("mode", "mechanism", "state", "submission"):
            _enum(f"data.{k}", f"data.{k}", data[k])
        if "id" not in data["qualification"]:
            _fail("data.qualification.id")
    elif ev["type"] == "eval.completed":
        _enum("data.verdict", "data.verdict", data["verdict"])
        _ref("data.artifact", data["artifact"])
    else:
        _enum("data.disposition", "data.disposition", data["disposition"])
        if ev["type"] == "seal.created":
            _ref("data.artifact", data["artifact"])
