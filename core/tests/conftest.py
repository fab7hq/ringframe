import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def repo(tmp_path):
    """A fresh git worktree root to act as a consumer workspace."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "README.md").write_text("fixture\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"],
        check=True,
    )
    return tmp_path


FIXTURE_CONFIG = Path(__file__).parent / "fixtures" / "config"


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path_factory, monkeypatch):
    """A real config home per test. The package ships none; this stands in for a synced bundle."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("ringframe-user")))
    from ringframe import workspace

    workspace.install_config(FIXTURE_CONFIG)


@pytest.fixture
def user_home(monkeypatch):
    """Re-point HOME at a fresh config home, for tests that want their own global layer."""
    from ringframe import workspace

    def use(path):
        monkeypatch.setenv("HOME", str(path))
        workspace.install_config(FIXTURE_CONFIG)
        return Path(path)

    return use
