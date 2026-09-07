"""Delta catalogs (ADR-0008): host deltas keyed by (host, capability); practice deltas keyed by classification.

Authored as YAML, rendered deterministically by the CLI. The model writes the task body; it never chooses or words
the standing rules. Verification of the work is rf:eval's, so no delta carries a check."""

import os
from importlib import resources
from pathlib import Path

from ringframe import config

_DIR = resources.files("ringframe") / "deltas"
SCHEMA = "ringframe.deltas/1"
HOST_STATUS = ("candidate", "qualified", "retired")
PRACTICE_STATUS = ("attributed", "candidate", "qualified", "retired")
TIERS = ("core", "situational", "reference")
DEFAULT_DOMAIN = "software-development"


def host_catalog_names() -> list[str]:
    return sorted(p.name[:-5] for p in _DIR.iterdir() if p.name.endswith(".yaml"))


def load_host_catalog(host: str) -> dict:
    cat = config.load_yaml_text((_DIR / f"{host}.yaml").read_text(encoding="utf-8"), f"deltas/{host}.yaml")
    _check(cat.get("schema") == SCHEMA and cat.get("scope") == "host" and cat.get("host") == host, f"deltas/{host}.yaml: not a host catalog")
    for e in cat.get("entries", []):
        _check(all(k in e for k in ("id", "capability", "text", "matrix_ref", "status")), f"deltas/{host}.yaml: entry {e.get('id')} incomplete")
        _check(e["status"] in HOST_STATUS, f"deltas/{host}.yaml: {e['id']} status {e['status']!r}")
    return cat


def load_practice_catalog(domain: str = DEFAULT_DOMAIN) -> dict:
    cat = config.load_yaml_text((_DIR / "practice" / f"{domain}.yaml").read_text(encoding="utf-8"), f"deltas/practice/{domain}.yaml")
    _check(cat.get("schema") == SCHEMA and cat.get("scope") == "practice", f"deltas/practice/{domain}.yaml: not a practice catalog")
    cat.setdefault("render", {}).setdefault("core_cap", 5)
    cat.setdefault("concerns", [])
    for e in cat.get("entries", []):
        _check("id" in e and "text" in e and "applies_to" in e, f"practice entry {e.get('id')} incomplete")
    return cat


def user_layer_path() -> Path:
    return Path(os.environ.get("HOME") or Path.home()) / ".fab7" / "rf" / "deltas.yaml"


def _layers(ws) -> list[dict]:
    out = []
    for root, path in (("user", user_layer_path()), ("workspace", ws.rf_dir / "deltas.yaml")):
        if path.exists():
            doc = config.load_yaml(path)
            _check(doc.get("schema") == SCHEMA, f"{path}: schema must be {SCHEMA}")
            out.append({"root": root, "path": str(path), "sha256": config.sha256_of(doc), "entries": doc.get("entries", [])})
    return out


def effective(ws, domain: str = DEFAULT_DOMAIN) -> dict:
    """id -> merged entry with the layer that last touched it. Overrides replace fields by id; new ids add entries."""
    shipped = load_practice_catalog(domain)
    merged = {e["id"]: {**e, "layer": "shipped"} for e in shipped["entries"]}
    for layer in _layers(ws):
        for o in layer["entries"]:
            _check("id" in o, f"{layer['path']}: override without id")
            base = merged.get(o["id"], {"applies_to": {}, "text": "", "principle": "team"})
            merged[o["id"]] = {**base, **o, "layer": layer["root"]}
    return merged


def _matches(entry: dict, classification: dict) -> bool:
    a = entry.get("applies_to", {})
    if a.get("task") and not set(a["task"]) & set(classification.get("task", [])):
        return False
    if a.get("result") and classification.get("result") not in a["result"]:
        return False
    if a.get("effects") and not set(a["effects"]) & set(classification.get("effects", [])):
        return False
    return True


def validate_concerns(concerns, domain: str = DEFAULT_DOMAIN) -> None:
    vocab = set(load_practice_catalog(domain)["concerns"])
    unknown = [c for c in (concerns or []) if c not in vocab]
    _check(not unknown, f"unknown concern(s) {unknown}; domain {domain} knows {sorted(vocab)}")


def render(ws, profile: dict, capability: str, classification: dict, *, statuses=("qualified",), domain: str = DEFAULT_DOMAIN) -> dict:
    """Deterministic delta block for one Ask: host lines for (profile.host, capability), then one practice paragraph."""
    # ---- host layer
    host_block = {"catalog_sha256": None, "deltas": [], "status_filter": list(statuses), "text": "", "entries": []}
    if profile.get("host") in host_catalog_names():
        cat = load_host_catalog(profile["host"])
        chosen = [e for e in cat["entries"] if e["capability"] == capability and e["status"] in statuses]
        host_block.update(catalog_sha256=config.sha256_of(cat), deltas=[e["id"] for e in chosen], text="\n".join(e["text"].strip() for e in chosen),
                          entries=[{"id": e["id"], "text": e["text"].strip()} for e in chosen])
    # ---- practice layer
    shipped = load_practice_catalog(domain)
    concerns = list(classification.get("concerns", []))
    validate_concerns(concerns, domain)
    merged = effective(ws, domain)
    cap_wants_subagents = bool(profile.get("subagents"))
    core, situational = [], []
    for order, (eid, e) in enumerate(merged.items()):
        if e.get("enabled") is False or e.get("status", "attributed") not in ("attributed", "qualified") or not _matches(e, classification):
            continue
        if e.get("requires", {}).get("host_capability") == "subagents" and not cap_wants_subagents:
            continue
        tier = e.get("tier", "situational")
        if tier == "core":
            core.append((e.get("priority", 100), order, e))
        elif tier == "situational" and set(e.get("concerns", [])) & set(concerns):
            situational.append((e.get("priority", 100), order, e))
    core.sort(key=lambda t: t[:2])
    situational.sort(key=lambda t: t[:2])
    cap = int(shipped["render"]["core_cap"])
    kept_core, dropped = core[:cap], [e["id"] for _, _, e in core[cap:]]
    selected = [e for _, _, e in kept_core + situational]
    practice_text = " ".join(" ".join(e["text"].split()) for e in selected)
    layers = _layers(ws)
    practice_block = {"domain": domain, "shipped_sha256": config.sha256_of(shipped), "layers": [{k: v for k, v in l.items() if k != "entries"} for l in layers],
                      "selected": [e["id"] for e in selected], "matched_concerns": [c for c in concerns if any(c in e.get("concerns", []) for e in selected)],
                      "dropped_by_budget": dropped, "text": practice_text,
                      "entries": [{"id": e["id"], "text": " ".join(e["text"].split())} for e in selected]}
    text = "\n".join(part for part in (host_block["text"], practice_text) if part)
    return {"text": text, "host": host_block, "practice": practice_block}


def _check(ok: bool, message: str) -> None:
    if not ok:
        raise config.ConfigError(message)
