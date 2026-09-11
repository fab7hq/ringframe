import os
from pathlib import Path

import pytest

from ringframe import config, workspace


def test_nested_project_keeps_its_own_root(repo):
    sub = repo / "a" / "b"
    sub.mkdir(parents=True)
    ws = workspace.resolve(cwd=sub)
    assert ws.root == sub.resolve()
    assert ws.rule == "cwd"
    ws.ensure()
    assert ws.rf_dir == sub.resolve() / ".fab7" / "rf"
    assert not (repo / ".fab7").exists()


def test_root_falls_back_to_cwd(tmp_path):
    ws = workspace.resolve(cwd=tmp_path)
    assert ws.root == tmp_path.resolve()
    assert ws.rule == "cwd"


def test_explicit_workspace_wins(repo, tmp_path):
    ws = workspace.resolve(cwd=repo, explicit=tmp_path)
    assert ws.root == tmp_path.resolve()
    assert ws.rule == "explicit"


def test_ensure_creates_self_ignoring_dir(repo):
    ws = workspace.resolve(cwd=repo)
    ws.ensure()
    assert (ws.rf_dir / ".gitignore").read_text() == "*\n"
    assert oct(ws.rf_dir.stat().st_mode & 0o777) == "0o700"
    assert (ws.rf_dir / "tmp").is_dir()
    ws.ensure()  # idempotent


def test_two_worktrees_two_ledgers(repo, tmp_path):
    import subprocess

    other = tmp_path / "wt"
    subprocess.run(["git", "-C", str(repo), "worktree", "add", "-q", str(other)], check=True)
    assert workspace.resolve(cwd=other).root == other.resolve()
    assert workspace.resolve(cwd=repo).root == repo.resolve()


# ---- Git is a hard requirement -----------------------------------------------------------------

def test_require_git_accepts_a_repo_with_a_commit(repo):
    workspace.require_git(workspace.resolve(cwd=repo))


def test_require_git_accepts_a_subdirectory_of_a_repo(repo):
    sub = repo / "nested"
    sub.mkdir()
    workspace.require_git(workspace.resolve(cwd=sub))


def test_require_git_rejects_a_plain_directory(tmp_path):
    import pytest

    with pytest.raises(workspace.WorkspaceError) as exc:
        workspace.require_git(workspace.resolve(cwd=tmp_path))
    assert exc.value.code == "workspace.no_git"
    assert "git init" in exc.value.detail


def test_require_git_rejects_a_repo_without_a_commit(tmp_path):
    import subprocess

    import pytest

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    with pytest.raises(workspace.WorkspaceError) as exc:
        workspace.require_git(workspace.resolve(cwd=tmp_path))
    assert exc.value.code == "workspace.no_commit"
    assert "commit" in exc.value.detail


def test_latest_bundle_tag_is_the_highest_version_not_the_first_listed():
    """The tags API promises no order, and 0.0.10 must beat 0.0.9."""
    names = ["v0.0.2", "v0.0.10", "v0.0.9", "vnope", "nightly"]
    assert workspace.latest_tag(names) == "v0.0.10"
    assert workspace.latest_tag(reversed(names)) == "v0.0.10"
    assert workspace.latest_tag(["nightly"]) is None


# ---- installing configuration ------------------------------------------------------------------

def _config(tmp_path, *, profile_schema="ringframe.profile/1", practice_schema="ringframe.deltas/1",
            bundle_schema="ringframe.bundle/1"):
    import shutil

    root = tmp_path / "bundle"
    shutil.rmtree(root, ignore_errors=True)
    (root / "harnesses").mkdir(parents=True)
    (root / "deltas" / "practices").mkdir(parents=True)
    (root / "bundle.yaml").write_text(f"schema: {bundle_schema}\nproduct: ringframe\nconfig_home: rf\n")
    (root / "harnesses" / "h1.yaml").write_text(
        f"schema: {profile_schema}\nprofile_id: h1\nhost: h1\ncapabilities: []\n")
    (root / "deltas" / "practices" / "software-development.yaml").write_text(
        f"schema: {practice_schema}\nscope: practice\ndomain: software-development\n"
        "description: d\nrender: {core_cap: 5}\nconcerns: [c]\nentries: []\n")
    return root


def _marketplace(tmp_path, bundle_schema="ringframe.bundle/1"):
    """The layout fab7 actually ships: bundle.yaml beside config/, not inside it."""
    product = tmp_path / "products" / "ringframe"
    product.mkdir(parents=True, exist_ok=True)
    config_dir = _config(tmp_path)
    import shutil

    shutil.rmtree(product / "config", ignore_errors=True)
    shutil.move(str(config_dir), str(product / "config"))
    (product / "config" / "bundle.yaml").unlink()
    (product / "bundle.yaml").write_text(f"schema: {bundle_schema}\nproduct: ringframe\nconfig_home: rf\n")
    return product / "config"


def test_install_reads_the_bundle_manifest_beside_the_config_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(workspace.WorkspaceError) as exc:
        workspace.install_config(_marketplace(tmp_path, bundle_schema="ringframe.bundle/999"))
    assert exc.value.code == "config.schema" and "999" in exc.value.detail
    assert not (config.config_dir() / "harnesses").exists()
    workspace.install_config(_marketplace(tmp_path))  # the same layout, readable schema
    assert (config.config_dir() / "harnesses" / "h1.yaml").exists()
    assert not (config.config_dir() / "bundle.yaml").exists()  # the mirror stays the config tree


def test_install_refuses_a_schema_it_cannot_read(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for kwargs in ({"profile_schema": "ringframe.profile/999"},
                   {"practice_schema": "ringframe.deltas/999"},
                   {"bundle_schema": "ringframe.bundle/999"}):
        with pytest.raises(workspace.WorkspaceError) as exc:
            workspace.install_config(_config(tmp_path, **kwargs))
        assert exc.value.code == "config.schema" and "999" in exc.value.detail
        assert not (config.config_dir() / "harnesses").exists()  # nothing written


def test_a_refused_install_leaves_the_working_configuration_intact(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    workspace.install_config(_config(tmp_path))
    before = (config.config_dir() / "harnesses" / "h1.yaml").read_text()
    with pytest.raises(workspace.WorkspaceError):
        workspace.install_config(_config(tmp_path, practice_schema="ringframe.deltas/999"))
    assert (config.config_dir() / "harnesses" / "h1.yaml").read_text() == before


def test_a_failed_replace_restores_the_previous_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    workspace.install_config(_config(tmp_path))
    installed = config.config_dir() / "harnesses" / "h1.yaml"   # before HOME can be restored
    before = installed.read_text()
    original = Path.rename

    failed = []

    def fail_replacing_target_once(self, target):
        if Path(target) == config.config_dir() and not failed:
            failed.append(True)
            raise OSError("injected rename failure")
        return original(self, target)

    monkeypatch.setattr(Path, "rename", fail_replacing_target_once)
    with pytest.raises(OSError, match="injected"):
        workspace.install_config(_config(tmp_path))
    monkeypatch.setattr(Path, "rename", original)
    assert installed.read_text() == before
