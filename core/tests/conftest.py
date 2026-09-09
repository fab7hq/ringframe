import subprocess

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


@pytest.fixture(autouse=True)
def isolated_user_config(tmp_path_factory, monkeypatch):
    # Delta reads use the user's on-disk catalog; tests never read or edit real config.
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("ringframe-user")))
