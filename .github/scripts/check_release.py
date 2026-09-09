"""Check release identities and built metadata; retain distribution checksums."""

import hashlib
import json
import sys
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "core"))
from ringframe import __version__


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def read_json(path):
    return json.loads((ROOT / path).read_text())


project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
version = project["version"]
require(project["name"] == "ringframe" and __version__ == version, "Python identity mismatch")
require(project["scripts"] == {"ringframe": "ringframe.cli:main"}, "CLI identity mismatch")
locked = [p for p in tomllib.loads((ROOT / "uv.lock").read_text())["package"] if p["name"] == "ringframe"]
require(len(locked) == 1 and locked[0]["version"] == version, "Lock version mismatch")
for host, manifest in (("claude", ".claude-plugin"), ("codex", ".codex-plugin")):
    plugin = read_json(f"plugins/{host}/{manifest}/plugin.json")
    require(plugin["name"] == "rf" and plugin["version"] == version, f"{host} plugin identity mismatch")
    market = read_json(f'{".claude-plugin" if host == "claude" else ".agents/plugins"}/marketplace.json')
    require(market["name"] == "ringframe" and len(market["plugins"]) == 1, f"{host} marketplace identity mismatch")
    entry = market["plugins"][0]
    source = entry["source"] if host == "claude" else entry["source"]["path"]
    require(entry["name"] == "rf" and source == f"./plugins/{host}", f"{host} marketplace source mismatch")
    if host == "claude":
        require(entry["version"] == version, "Claude marketplace version mismatch")

dist = Path(sys.argv[1])
wheels, sdists = list(dist.glob("*.whl")), list(dist.glob("*.tar.gz"))
require(len(wheels) == len(sdists) == 1, "Expected one wheel and one sdist")
with zipfile.ZipFile(wheels[0]) as archive:
    metadata, = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
    wheel_metadata = archive.read(metadata)
with tarfile.open(sdists[0]) as archive:
    metadata, = [m for m in archive.getmembers() if m.name.count("/") == 1 and m.name.endswith("/PKG-INFO")]
    sdist_metadata = archive.extractfile(metadata).read()
for raw in (wheel_metadata, sdist_metadata):
    metadata = BytesParser().parsebytes(raw)
    require(metadata["Name"] == "ringframe" and metadata["Version"] == version, "Distribution identity mismatch")
    require(metadata["Description-Content-Type"] == "text/markdown", "README content type mismatch")
    require(metadata.get_payload().strip() == (ROOT / "README.md").read_text().strip(), "Distribution README mismatch")

checksums = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {dist.name}/{p.name}\n" for p in sorted(wheels + sdists)]
(dist.parent / "SHA256SUMS").write_text("".join(checksums))
print(f"Release identities and distributions match ringframe {version}")
