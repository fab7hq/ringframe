"""Authored configuration is YAML; evidence is canonical JSON (ADR-0008 §7).

Identities of configuration documents are digests of the parsed document's canonical JSON,
so comments and formatting never change a profile or catalog identity."""

from pathlib import Path

import yaml

from ringframe import digest
from ringframe.store import canonical


class ConfigError(Exception):
    pass


def load_yaml_text(text: str, where: str = "<text>") -> dict:
    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError(f"{where}: {e}") from None
    if not isinstance(doc, dict):
        raise ConfigError(f"{where}: top level must be a mapping")
    return doc


def load_yaml(path: Path | str) -> dict:
    path = Path(path)
    return load_yaml_text(path.read_text(encoding="utf-8"), str(path))


def sha256_of(doc: dict) -> str:
    return digest.sha256_bytes(canonical(doc))
