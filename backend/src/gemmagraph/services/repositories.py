import hashlib
import json
import stat
import zipfile
from io import BytesIO
from pathlib import Path, PurePosixPath
from uuid import uuid4

from gemmagraph.db import now, uid
from gemmagraph.errors import AppError
from gemmagraph.queue import enqueue
from gemmagraph.services.workspaces import is_public, tree_hash


class Repositories:
    def __init__(self, db, settings, workspaces):
        self.db, self.settings, self.workspaces = db, settings, workspaces

    async def import_zip(self, name, raw):
        if len(raw) > 50 * 1024 * 1024:
            raise AppError("upload_too_large", "压缩包不能超过 50 MB", 413)
        try:
            archive = zipfile.ZipFile(BytesIO(raw))
            members = archive.infolist()
        except (zipfile.BadZipFile, OSError) as e:
            raise AppError("invalid_zip", "无法读取仓库 ZIP 文件") from e
        if len(members) > 20000 or sum(x.file_size for x in members) > 500 * 1024 * 1024:
            raise AppError("archive_too_large", "仓库文件数或解压总量超过限制", 413)
        snapshot_id = "src_" + uuid4().hex[:20]
        dest = self.workspaces.source(snapshot_id)
        dest.mkdir(parents=True)
        seen, total, included_files = set(), 0, 0
        try:
            for item in members:
                name_in_zip = item.filename.rstrip("/")
                if not name_in_zip:
                    continue
                p = PurePosixPath(name_in_zip)
                if p.is_absolute() or ".." in p.parts or "\\" in item.filename or "\x00" in item.filename:
                    raise AppError("invalid_zip_path", "ZIP 包含越界文件路径")
                mode = item.external_attr >> 16
                if stat.S_ISLNK(mode):
                    raise AppError("invalid_zip_path", "ZIP 不允许包含符号链接")
                relative = Path(*p.parts)
                key = relative.as_posix().casefold()
                if key in seen:
                    raise AppError("duplicate_zip_path", "ZIP 包含重复文件路径")
                seen.add(key)
                if item.is_dir() or not is_public(relative.as_posix()):
                    continue
                total += item.file_size
                if item.file_size > 8 * 1024 * 1024 or total > 300 * 1024 * 1024:
                    raise AppError("archive_file_too_large", "单文件或有效源码总量超过限制", 413)
                if item.compress_size == 0 and item.file_size > 0 or (
                    item.compress_size > 0 and item.file_size / item.compress_size > 250
                ):
                    raise AppError("suspicious_zip", "ZIP 压缩比例超过限制", 413)
                target = dest.joinpath(*p.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open("xb") as output:
                    payload = source.read(item.file_size + 1)
                    if len(payload) != item.file_size:
                        raise AppError("invalid_zip", "ZIP 文件大小与目录记录不一致")
                    output.write(payload)
                included_files += 1
        except Exception:
            import shutil
            shutil.rmtree(dest, ignore_errors=True)
            raise
        digest = tree_hash(dest)
        repository = dict(id=uid("repo_"), name=Path(name).stem[:100] or "repository",
                          snapshot_id=snapshot_id, tree_hash=digest, created_at=now(),
                          index_status="queued", file_count=included_files, symbol_count=0,
                          parse_coverage=None, diagnostics=[])
        async with self.db.transaction() as c:
            await c.execute("INSERT INTO resources VALUES('repository',?,?)",
                            (repository["id"], json.dumps(repository, ensure_ascii=False)))
            await enqueue(c, "index", repository["id"])
        return repository

    async def file(self, repository, relative, start=1, end=None):
        from gemmagraph.services.workspaces import resolve_inside
        path = resolve_inside(self.workspaces.source(repository["snapshot_id"]), relative)
        if not is_public(relative) or not path.is_file() or path.stat().st_size > 1_000_000:
            raise AppError("file_unavailable", "文件不存在、过大或属于受保护内容", 404)
        try:
            lines = path.read_text().splitlines()
        except UnicodeDecodeError as e:
            raise AppError("binary_file", "该文件不是 UTF-8 文本", 415) from e
        start = max(1, min(start, len(lines) or 1))
        stop = min(len(lines), end or start + 250, start + 500)
        return {"path": relative, "start_line": start, "end_line": stop,
                "content": "\n".join(lines[start - 1:stop]), "total_lines": len(lines),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
