"""Host capability profiles shipped with the core."""

from importlib import resources

from ringframe import config

_DIR = resources.files("ringframe") / "profiles"


def load(name: str) -> dict:
    return config.load_yaml_text((_DIR / f"{name}.yaml").read_text(encoding="utf-8"), f"profiles/{name}.yaml")


def sha256(name: str) -> str:
    return config.sha256_of(load(name))


def names() -> list[str]:
    return sorted(p.name[:-5] for p in _DIR.iterdir() if p.name.endswith(".yaml"))


def for_host(host: dict) -> dict:
    """Select integration rules by host identity; versions are provenance only."""
    for name in names():
        p = load(name)
        if p["host"] is not None and p["host"] == host.get("name"):
            return p
    return load("unknown")


def capability(profile: dict, cap_id: str) -> dict | None:
    return next((c for c in profile["capabilities"] if c["id"] == cap_id), None)
