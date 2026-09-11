"""Workspace root resolution and the .fab7/rf/ directory."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class WorkspaceError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


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


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True)


def require_git(ws: Workspace) -> None:
    """Git is a hard requirement: Eval diffs it and Seal names a commit as the subject.

    Refused here rather than at Eval, so that no Ask is ever recorded in a
    workspace whose work could not later be evaluated or sealed.
    """
    try:
        _git(ws.root, "rev-parse", "--git-dir")
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise WorkspaceError(
            "workspace.no_git",
            f"{ws.root} is not in a Git repository; RingFrame evaluates and seals the Git delta. "
            "Run `git init` and make one commit, or run from a repository.",
        ) from None
    try:
        _git(ws.root, "rev-parse", "--verify", "--quiet", "HEAD")
    except subprocess.CalledProcessError:
        raise WorkspaceError(
            "workspace.no_commit",
            f"{ws.root} is a Git repository with no commit; RingFrame needs one commit to anchor an Eval. "
            "Make the first commit, then retry.",
        ) from None


# Every file that crosses the boundary names the schema it is written to, and these are
# the versions this release reads. Nothing else gates on a version (ADR-0012).
BUNDLE_SCHEMA = "ringframe.bundle/1"
PROFILE_SCHEMA = "ringframe.profile/1"
DELTAS_SCHEMA = "ringframe.deltas/1"

BUNDLE_REPO = "fab7hq/fab7"
BUNDLE_PRODUCT = "ringframe"  # this CLI's subtree in the marketplace
BUNDLE_TAG_PREFIX = "v"       # the marketplace releases as a whole, so tags are plain versions


def _version_key(tag: str) -> tuple:
    """Sort key for `vX.Y.Z`. Unparseable tags sort lowest rather than raising."""
    try:
        return (1, tuple(int(part) for part in tag[len(BUNDLE_TAG_PREFIX):].split(".")))
    except ValueError:
        return (0, ())


def latest_tag(names) -> str | None:
    """The highest `vX.Y.Z`. The API does not promise an order, so never take the first."""
    matching = [n for n in names if n.startswith(BUNDLE_TAG_PREFIX)]
    return max(matching, key=_version_key, default=None)


def _latest_tag() -> str:
    import json
    from urllib.request import urlopen

    with urlopen(f"https://api.github.com/repos/{BUNDLE_REPO}/tags", timeout=30) as r:
        tags = json.load(r)
    tag = latest_tag(t["name"] for t in tags)
    if not tag:
        raise WorkspaceError("config.no_release", f"{BUNDLE_REPO} has no {BUNDLE_TAG_PREFIX}* release tag")
    return tag


def _download(dest: Path) -> tuple[str, str | None]:
    """Extract products/<product>/config into dest. Returns the tag and the bundle manifest text."""
    import io
    import tarfile
    from urllib.request import urlopen

    tag = _latest_tag()
    url = f"https://codeload.github.com/{BUNDLE_REPO}/tar.gz/refs/tags/{tag}"
    with urlopen(url, timeout=120) as r:
        raw = r.read()
    inner = f"products/{BUNDLE_PRODUCT}/config/"
    manifest = f"products/{BUNDLE_PRODUCT}/bundle.yaml"
    bundle = None
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        members = [m for m in tf.getmembers() if m.isfile() and inner in m.name]
        if not members:
            raise WorkspaceError("config.bundle", f"{tag} contains no {inner}")
        for m in members:
            rel = Path(m.name.split(inner, 1)[1])
            if rel.is_absolute() or ".." in rel.parts:
                raise WorkspaceError("config.bundle", f"unsafe path in bundle: {m.name}")
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tf.extractfile(m).read())
        # The manifest sits beside config/, so it is read but never mirrored: the installed
        # tree stays exactly the config/ tree.
        found = next((m for m in tf.getmembers() if m.isfile() and m.name.endswith(manifest)), None)
        if found is not None:
            bundle = tf.extractfile(found).read().decode("utf-8")
    return tag, bundle


def _bundle_manifest(source: Path) -> str | None:
    """The manifest the marketplace keeps beside config/, or inside it if someone puts it there."""
    for candidate in (source.parent / "bundle.yaml", source / "bundle.yaml"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return None


def _validate(staged: Path, bundle: str | None) -> None:
    """Every file must name a schema this release reads, before anything is replaced."""
    from ringframe import config

    for rel in ("harnesses", "deltas/practices"):
        if not (staged / rel).is_dir():
            raise WorkspaceError("config.bundle", f"configuration has no {rel}/ directory")
    if bundle is not None:
        found = config.load_yaml_text(bundle, "bundle.yaml").get("schema")
        if found != BUNDLE_SCHEMA:
            raise WorkspaceError(
                "config.schema",
                f"bundle.yaml declares {found!r}; this release reads {BUNDLE_SCHEMA!r}. "
                "Upgrade ringframe, or install a configuration it can read.")
    expected = [(p, PROFILE_SCHEMA) for p in sorted((staged / "harnesses").glob("*.yaml"))]
    expected += [(p, DELTAS_SCHEMA) for p in sorted((staged / "deltas").glob("*.yaml"))]
    expected += [(p, DELTAS_SCHEMA) for p in sorted((staged / "deltas" / "practices").glob("*.yaml"))]
    for path, schema in expected:
        try:
            found = config.load_yaml(path, allow_empty=True).get("schema")
        except config.ConfigError as exc:
            raise WorkspaceError("config.unreadable", f"{path.name}: {exc}") from None
        if found != schema:
            raise WorkspaceError(
                "config.schema",
                f"{path.name} declares {found!r}; this release reads {schema!r}. "
                "Upgrade ringframe, or install a configuration it can read.")


def _replace(staged: Path, target: Path) -> None:
    """Swap in the staged tree, putting the previous one back if the swap fails."""
    import shutil

    previous = target.with_name(f".previous-{os.getpid()}") if target.exists() else None
    if previous is not None:
        target.rename(previous)
    try:
        staged.rename(target)
    except Exception:
        if previous is not None:
            previous.rename(target)
        raise
    if previous is not None:
        shutil.rmtree(previous, ignore_errors=True)


def install_config(source: Path | None = None) -> dict:
    """Replace the synced config layer; create the overrides layer once and never touch it again."""
    import shutil
    import tempfile

    from ringframe import config

    home_dir = config.home()
    home_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(home_dir, 0o700)
    staged = Path(tempfile.mkdtemp(dir=home_dir, prefix=".staging-"))
    try:
        if source is not None:
            src = Path(source).resolve()
            if not (src / "harnesses").is_dir():
                raise WorkspaceError("config.source", f"{src} has no harnesses/ directory")
            shutil.copytree(src, staged, dirs_exist_ok=True)
            bundle, revision = _bundle_manifest(src), "local"
        else:
            revision, bundle = _download(staged)
        _validate(staged, bundle)
        (staged / ".revision").write_text(revision + "\n", encoding="utf-8")
        _replace(staged, config.config_dir())
    finally:
        shutil.rmtree(staged, ignore_errors=True)
    overrides = config.overrides_dir() / "deltas" / "practices"
    overrides.mkdir(parents=True, exist_ok=True)
    return {"rf_dir": str(home_dir), "config": str(config.config_dir()),
            "overrides": str(config.overrides_dir()), "revision": revision}
