"""CLI conversation views. Stored artifacts and full fetch results stay unchanged."""


def pick(data, keys):
    return {key: data[key] for key in keys if key in data}


ASK_KEYS = ("ask_id", "title", "state", "capability")
DOMAIN_KEYS = ("domain", "base", "description", "concerns", "project_opted_in")


def candidates(items):
    return [pick(item, ASK_KEYS) for item in items]


def _capability(data):
    result = pick(data, ("id", "selection", "effects", "delivery_mode", "continuation",
                         "limitations", "requires_explicit_request_for_effects"))
    for field, keys in (("confirmation", ("tool", "requires_feature")),
                        ("activation", ("mechanism", "tool")),
                        ("receipt", ("captured_by", "tool"))):
        value = {k: v for k, v in pick(data.get(field) or {}, keys).items() if v is not None}
        if value:
            result[field] = value
    return result


def _profile(data):
    return {"host": data["host"], "routing": pick(data["routing"], ("guidance", "precedence")),
            "capabilities": [_capability(c) for c in data["capabilities"]]}


def _delta_list(data):
    if "practice" not in data:
        return {key: pick(entry, ("id", "label", "text")) for key, entry in data.items()}
    return {"host": [pick(e, ("id", "label", "text", "capability")) for e in data["host"]],
            "practice": [pick(e, ("id", "label", "text")) for e in data["practice"]],
            "concerns": data["concerns"]}


# Every fetch has an explicit conversation view; no full-result fallback.
FETCH = {
    ("profile", "show"): _profile,
    ("deltas", "domains"): lambda d: {"domains": [pick(x, DOMAIN_KEYS) for x in d["domains"]]},
    ("deltas", "list"): _delta_list,
    ("deltas", "render"): lambda d: d["text"],
    ("ask", "list"): lambda d: {"asks": candidates(d["asks"])},
    ("ask", "show"): lambda d: pick(d, (*ASK_KEYS, "prompt_path", "source_verified")),
    ("ask", "resolve"): lambda d: {"rule_applied": d["rule_applied"], "candidates": candidates(d["candidates"])},
    ("eval", "list"): lambda d: {"evals": [pick(e, ("eval_id", "verdict", "confidence", "state", "basis")) for e in d["evals"]]},
    ("seal", "check"): lambda d: pick(d, ("seal_id", "fresh", "subject_matches", "codes")),
    ("ledger", "verify"): lambda d: pick(d, ("clean", "findings")),
}


def _eval_open(data):
    return {**pick(data, ("eval_id", "brief_path", "changes")),
            "brief": pick(data["brief"], ("sha256",)),
            "anchor": data["anchor"]["ref"], "subject": data["subject"]["kind"]}


def _eval_close(data):
    return {**pick(data, ("eval_id", "verdict", "confidence", "items", "drift", "delta", "limitations")),
            "basis": pick(data["basis"], ("unrecorded_prompts",))}


def _seal(data):
    return {**pick(data, ("seal_id", "disposition", "asks", "limitations")),
            "eval": pick(data["eval"], ("eval_id", "verdict", "confidence", "subject_matches")) if data["eval"] else None}


def _capture(data):
    result = pick(data, ("captured",))
    if data.get("submission"):
        result["submission"] = pick(data["submission"], ("ask_id", "state"))
    return result


# Actions have one sufficient response, with no output-mode flags.
ACTION = {
    ("init", None): lambda d: pick(d, ("rf_dir", "config", "revision")),
    ("sync", None): lambda d: pick(d, ("config", "revision")),
    ("ask", "compile"): lambda d: pick(d, ("ask_id", "prompt_path", "delivery_mode", "source_verified")),
    ("ask", "copy"): lambda d: d,
    ("ask", "confirm"): lambda d: pick(d, ("ask_id", "confirmation")),
    ("ask", "cancel"): lambda d: {"ask_id": d["ask_id"], "state": "cancelled"},
    ("ask", "submitted"): lambda d: pick(d, ("ask_id", "state", "as_modified")),
    ("ask", "delivery"): lambda d: pick(d, ("ask_id", "mode", "state", "recorded", "error")) if isinstance(d, dict) else d,
    ("eval", "open"): _eval_open,
    ("eval", "close"): _eval_close,
    ("seal", "create"): _seal,
    ("sessions", "capture"): _capture,
    ("sessions", "prune"): lambda d: pick(d, ("removed",)),
    ("export", None): lambda d: pick(d, ("ask_id", "out", "files")),
}


def project(ns, result, ws):
    key = (ns.cmd, getattr(ns, "sub", None))
    if key in FETCH:
        return FETCH[key](result) if ns.minimal else result
    result = ACTION[key](result)
    if key == ("seal", "create"):
        result["receipt_path"] = str(ws.rf_dir / f"seals/{result['seal_id']}.json")
    return result
