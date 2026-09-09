"""Release metadata must preserve the UTF-8 README in both distributions."""
import io
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path


def test_release_check_preserves_utf8_readme(tmp_path):
    root = Path(__file__).resolve().parents[2]
    version = tomllib.loads((root / 'pyproject.toml').read_text())['project']['version']
    readme = (root / 'README.md').read_bytes()
    metadata = (f'Name: ringframe\nVersion: {version}\n'
                'Description-Content-Type: text/markdown\n\n').encode() + readme
    dist = tmp_path / 'dist'
    dist.mkdir()
    with zipfile.ZipFile(dist / f'ringframe-{version}-py3-none-any.whl', 'w') as archive:
        archive.writestr(f'ringframe-{version}.dist-info/METADATA', metadata)
    with tarfile.open(dist / f'ringframe-{version}.tar.gz', 'w:gz') as archive:
        entry = tarfile.TarInfo(f'ringframe-{version}/PKG-INFO')
        entry.size = len(metadata)
        archive.addfile(entry, io.BytesIO(metadata))
    result = subprocess.run(
        [sys.executable, str(root / '.github/scripts/check_release.py'), str(dist)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert len((tmp_path / 'SHA256SUMS').read_text().splitlines()) == 2
