import hashlib
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact_ref(role: str, rel_path: str, path: Path) -> dict:
    return {"role": role, "path": rel_path, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
