"""Workspace root resolution and the .fab7/rf/ directory."""

import os
import subprocess
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
        return self

    def describe(self) -> dict:
        return {"root": str(self.root), "rule": self.rule}


def resolve(cwd: Path | None = None, explicit: Path | None = None) -> Workspace:
    if explicit is not None:
        return Workspace(Path(explicit).resolve(), "explicit")
    cwd = Path(cwd or os.getcwd())
    try:
        out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        return Workspace(Path(out).resolve(), "git_toplevel")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Workspace(cwd.resolve(), "cwd")
