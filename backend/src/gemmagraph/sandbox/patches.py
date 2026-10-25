import re
from pathlib import Path

from gemmagraph.errors import AppError
from gemmagraph.services.workspaces import safe_relative

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)$")


def validate(diff, allowed_paths, max_files=5):
    if not isinstance(diff, str) or "\x00" in diff or len(diff.encode()) > 120_000:
        return {"valid": False, "message": "补丁超过 120 KB"}
    try:
        files = _file_headers(diff)
        if not files or len(set(files)) > max_files:
            raise AppError("invalid_patch", "补丁为空或涉及文件数超限")
        for name in files:
            path = safe_relative(name)
            protected = {"tests", "test", "benchmarks", "fixtures", ".github", ".git"}
            if path != name or not path.endswith(".py") or protected.intersection(Path(path).parts) or any(
                part.startswith(".env") for part in Path(path).parts
            ) or Path(path).name in {"conftest.py", "setup.py"}:
                return {"valid": False, "message": f"禁止修改受保护路径：{name}"}
            if path not in allowed_paths:
                return {"valid": False, "message": f"不在允许路径内：{name}"}
    except AppError as e:
        return {"valid": False, "message": e.message}
    return {"valid": True, "message": "补丁格式与路径通过检查", "files": sorted(set(files))}


def _file_headers(diff):
    """Accept text-only, same-path unified diffs with complete hunk counts.

    Both old and new paths matter: git apply can otherwise rename/remove a
    protected file while presenting an allowed +++ destination to a validator.
    """
    lines, files, index = diff.splitlines(), [], 0
    announced = None
    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue
        if line.startswith("diff --git "):
            match = re.fullmatch(r"diff --git a/(.+) b/(.+)", line)
            if not match or match[1] != match[2]:
                raise AppError("invalid_patch", "不支持重命名、复制或带引号的路径")
            announced = match[1]
            index += 1
            continue
        if re.fullmatch(r"index [0-9a-f]+\.\.[0-9a-f]+(?: 100(?:644|755))?", line):
            index += 1
            continue
        if not line.startswith("--- a/") or index + 1 >= len(lines) or not lines[index + 1].startswith("+++ b/"):
            raise AppError("invalid_patch", "仅支持现有文件的统一文本 Diff；禁止模式变更、新建、删除或重命名")
        old, new = line[6:], lines[index + 1][6:]
        if old != new or (announced is not None and old != announced):
            raise AppError("invalid_patch", "补丁的新旧路径必须一致")
        safe_relative(old)
        files.append(old)
        announced = None
        index += 2
        hunks = 0
        while index < len(lines) and lines[index].startswith("@@ "):
            match = HUNK.fullmatch(lines[index])
            if not match:
                raise AppError("invalid_patch", "Diff 变更块头格式无效")
            old_remaining = int(match[2] if match[2] is not None else 1)
            new_remaining = int(match[4] if match[4] is not None else 1)
            index += 1
            while old_remaining or new_remaining:
                if index >= len(lines):
                    raise AppError("invalid_patch", "Diff 变更块行数不足")
                current = lines[index]
                if current == r"\ No newline at end of file":
                    index += 1
                    continue
                if not current or current[0] not in " +-":
                    raise AppError("invalid_patch", "Diff 变更块内容无效")
                old_remaining -= current[0] in " -"
                new_remaining -= current[0] in " +"
                if min(old_remaining, new_remaining) < 0:
                    raise AppError("invalid_patch", "Diff 变更块行数与头部不一致")
                index += 1
            if index < len(lines) and lines[index] == r"\ No newline at end of file":
                index += 1
            hunks += 1
        if not hunks:
            raise AppError("invalid_patch", "Diff 缺少有效变更块")
    if announced is not None:
        raise AppError("invalid_patch", "Diff 文件头缺少对应变更块")
    return files


async def apply(root: Path, diff_path: Path):
    proc = await __import__("asyncio").create_subprocess_exec(
        "git", "apply", "--check", str(diff_path), cwd=root,
        stdout=__import__("asyncio").subprocess.PIPE,
        stderr=__import__("asyncio").subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode:
        return {"ok": False, "stderr": err.decode(errors="replace")}
    proc = await __import__("asyncio").create_subprocess_exec(
        "git", "apply", str(diff_path), cwd=root,
        stdout=__import__("asyncio").subprocess.PIPE,
        stderr=__import__("asyncio").subprocess.PIPE,
    )
    _, err = await proc.communicate()
    return {"ok": proc.returncode == 0, "stderr": err.decode(errors="replace")}
