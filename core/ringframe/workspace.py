"""Workspace root resolution and the .fab7/rf/ directory."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workspace:
    root: Path
    rule: str

    @property
    def rf_dir(self) -> Path:
        return self.root / ".fab7" / "rf"

    def ensure(self) -> "Workspace":
        self.rf_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.rf_dir, 0o700)
        ignore = self.rf_dir / ".gitignore"
        if not ignore.exists():
            ignore.write_text("*\n")
        for sub in ("tmp", "asks", "evals", "seals", "sessions"):
            (self.rf_dir / sub).mkdir(exist_ok=True)
        from ringframe import deltas
        deltas.initialize(self.rf_dir)
        return self

    def describe(self) -> dict:
        return {"root": str(self.root), "rule": self.rule}


def resolve(cwd: Path | None = None, explicit: Path | None = None) -> Workspace:
    if explicit is not None:
        return Workspace(Path(explicit).resolve(), "explicit")
    return Workspace(Path(cwd or os.getcwd()).resolve(), "cwd")


def initialize_user() -> dict:
    """Initialize global delta catalogs; profiles stay in the installed package."""
    from ringframe import deltas

    root = deltas.user_root()
    paths = deltas.initialize(root, global_scope=True)
    # Retain the 0.0.2 JSON key as an alias; all configuration lives under rf.
    return {"rf_dir": str(root), "rt_dir": str(root), "deltas": paths}
