"""Host capability profiles, read from the global config home."""

from ringframe import config


def _dir():
    return config.require_config() / "harnesses"


def load(name: str) -> dict:
    doc = config.load_yaml_text((_dir() / f"{name}.yaml").read_text(encoding="utf-8"), f"harnesses/{name}.yaml")
    from ringframe.workspace import PROFILE_SCHEMA

    if doc.get("schema") != PROFILE_SCHEMA:
        raise config.ConfigError(
            f"harnesses/{name}.yaml declares {doc.get('schema')!r}; this release reads {PROFILE_SCHEMA!r}")
    return doc


def sha256(name: str) -> str:
    return config.sha256_of(load(name))


def names() -> list[str]:
    return sorted(p.name[:-5] for p in _dir().iterdir() if p.name.endswith(".yaml"))


def for_host(host: dict) -> dict:
    """Select integration rules by host identity; versions are provenance only."""
    for name in names():
        p = load(name)
        if p["host"] is not None and p["host"] == host.get("name"):
            return p
    return load("unknown")


def capability(profile: dict, cap_id: str) -> dict | None:
    return next((c for c in profile["capabilities"] if c["id"] == cap_id), None)
