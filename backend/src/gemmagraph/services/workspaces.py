import hashlib
import shutil
from pathlib import Path, PurePosixPath

from gemmagraph.errors import AppError

IGNORED = {".git", ".venv", "node_modules", "__pycache__", "dist", "build", ".pytest_cache"}


def safe_relative(value: str) -> str:
    p = PurePosixPath(value)
    if not value or "\\" in value or "\x00" in value or p.is_absolute() or ".." in p.parts:
        raise AppError("invalid_path", "路径必须位于仓库内部")
    return str(p)


def is_public(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return not any(p in IGNORED or p.startswith(".env") or p.endswith((".pem", ".key"))
                   or p in {"credentials", "id_rsa", "id_ed25519"} for p in parts)


def resolve_inside(root: Path, relative: str) -> Path:
    p = root / safe_relative(relative)
    if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):
        raise AppError("invalid_path", "路径超出工作区")
    return p


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        relative = p.relative_to(root).as_posix()
        if p.is_file() and is_public(relative):
            if p.is_symlink():
                raise AppError("invalid_path", "仓库不能包含符号链接")
            digest.update(relative.encode() + b"\0" + p.read_bytes() + b"\0")
    return digest.hexdigest()


class Workspaces:
    def __init__(self, settings):
        self.root = settings.data_dir.resolve()
        for folder in ("sources", "indexes", "workspaces", "artifacts", "exports"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def source(self, snapshot_id):
        return resolve_inside(self.root / "sources", snapshot_id)

    def workspace(self, run_id):
        return resolve_inside(self.root / "workspaces", run_id)

    def reset(self, run_id, snapshot_id):
        target = self.workspace(run_id)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(self.source(snapshot_id), target, symlinks=False)
        return target
