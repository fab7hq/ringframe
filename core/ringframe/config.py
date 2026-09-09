"""Authored configuration is YAML; evidence is canonical JSON.

Identities of configuration documents are digests of the parsed document's canonical JSON,
so comments and formatting never change a profile or catalog identity."""

from copy import deepcopy
from pathlib import Path

import yaml

from ringframe import digest
from ringframe.store import canonical


class ConfigError(Exception):
    pass


def load_yaml_text(text: str, where: str = "<text>", *, allow_empty=False) -> dict:
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError(f"{where}: {e}") from None
    if doc is None and allow_empty:
        return {}
    if not isinstance(doc, dict):
        raise ConfigError(f"{where}: top level must be a mapping")
    return doc


def load_yaml(path: Path | str, *, allow_empty=False) -> dict:
    path = Path(path)
    return load_yaml_text(path.read_text(encoding="utf-8"), str(path), allow_empty=allow_empty)


def sha256_of(doc: dict) -> str:
    return digest.sha256_bytes(canonical(doc))


def merge(base, override):
    """Recursive mappings and id-keyed lists; all other values are replaced."""
    if isinstance(base, dict) and isinstance(override, dict):
        result = deepcopy(base)
        for key, value in override.items():
            result[key] = merge(result[key], value) if key in result else deepcopy(value)
        return result
    if (isinstance(base, list) and isinstance(override, list) and override
            and all(isinstance(item, dict) and "id" in item for item in base + override)):
        result = {item["id"]: deepcopy(item) for item in base}
        for item in override:
            key = item["id"]
            result[key] = merge(result[key], item) if key in result else deepcopy(item)
        return list(result.values())
    return deepcopy(override)
