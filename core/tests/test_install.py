"""Installer routing: local source requires an explicit flag."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("args", [[], ["--source"]])
def test_installer_selects_registry_or_explicit_source_from_another_cwd(tmp_path, args):
    checkout = tmp_path / "source checkout"
    (checkout / "core/ringframe").mkdir(parents=True)
    (checkout / "core/ringframe/cli.py").touch()
    shutil.copyfile(Path(__file__).resolve().parents[2] / "install.sh", checkout / "install.sh")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    uv = bin_dir / "uv"
    uv.write_text('''#!/bin/sh
set -eu
if [ "$1 $2" = "tool install" ]; then
    for arg do package="$arg"; done
    printf '%s' "$package" > "$INSTALL_RECORD"
elif [ "$1 $2" = "tool dir" ]; then
    printf '%s\\n' "$TEST_BIN"
else
    exit 1
fi
''')
    cli = bin_dir / "ringframe"
    cli.write_text('''#!/bin/sh
set -eu
# Verify initialization uses the selected installed package.
[ "$(cat "$INSTALL_RECORD")" = "$EXPECTED_SOURCE" ] || exit 1
[ "$1 $2" = "init --global" ]
''')
    uv.chmod(0o755)
    cli.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "TEST_BIN": str(bin_dir),
           "INSTALL_RECORD": str(tmp_path / "installed"), "EXPECTED_SOURCE": str(checkout) if args else "git+https://github.com/fab7hq/ringframe@main"}
    result = subprocess.run(["sh", str(checkout / "install.sh"), *args], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
