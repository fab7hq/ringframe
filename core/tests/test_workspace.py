import os

from ringframe import workspace


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
