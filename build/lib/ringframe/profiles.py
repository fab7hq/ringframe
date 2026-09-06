"""Host capability profiles shipped with the core."""

import json
import re
from importlib import resources

from ringframe import digest

_DIR = resources.files("ringframe") / "profiles"


def _raw(name: str) -> bytes:
    return (_DIR / f"{name}.json").read_bytes()


def load(name: str) -> dict:
    return json.loads(_raw(name))


def sha256(name: str) -> str:
    return digest.sha256_bytes(_raw(name))


def names() -> list[str]:
    return sorted(p.name[:-5] for p in _DIR.iterdir() if p.name.endswith(".json"))


def _version(v: str) -> tuple:
    m = re.search(r"\d+(?:\.\d+)+", v)
    return tuple(int(x) for x in m.group(0).split(".")) if m else ()


def _in_range(version: str, spec: str) -> bool:
    v = _version(version)
    for clause in spec.split():
        op = clause[:2] if clause[1] in "=<>" else clause[0]
        bound = _version(clause[len(op):])
        ok = {"<": v < bound, "<=": v <= bound, ">": v > bound, ">=": v >= bound, "==": v == bound}[op]
        if not ok:
            return False
    return True


def for_host(host: dict) -> dict:
    for name in names():
        p = load(name)
        if p["host"] == host.get("name") and _in_range(str(host.get("version", "")), p["version_range"]):
            return p
    return load("unknown")


def capability(profile: dict, cap_id: str) -> dict | None:
    return next((c for c in profile["capabilities"] if c["id"] == cap_id), None)
