import hashlib
import json

from gemmagraph.db import now, uid
from gemmagraph.errors import AppError


class Datasets:
    def __init__(self, db):
        self.db = db

    async def import_jsonl(self, name, raw, repository_map):
        if len(raw) > 5 * 1024 * 1024:
            raise AppError("upload_too_large", "任务清单不能超过 5 MB", 413)
        try:
            text = raw.decode("utf-8-sig")
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise AppError("invalid_dataset", "任务清单必须是有效 UTF-8 JSONL") from e
        if not records or len(records) > 10000:
            raise AppError("invalid_dataset", "任务数必须在 1 到 10,000 之间")
        seen, tasks = set(), []
        for i, item in enumerate(records, 1):
            key, issue = item.get("instance_id"), item.get("issue")
            repo_key = item.get("repository_key")
            repo_id = item.get("repository_id") or repository_map.get(repo_key)
            if not key or key in seen or not isinstance(issue, str) or len(issue) < 5:
                raise AppError("invalid_dataset", f"第 {i} 行缺少唯一 instance_id 或有效 issue")
            if not repo_id:
                raise AppError("missing_repository_map", f"第 {i} 行的仓库 {repo_key!r} 未映射")
            repo = await self.db.get("repository", repo_id)
            if item.get("source_snapshot_hash") and item["source_snapshot_hash"] != repo["tree_hash"]:
                raise AppError("snapshot_mismatch", f"第 {i} 行与仓库快照哈希不匹配")
            profile = item.get("test_profile_id", "python-pytest")
            if profile != "python-pytest":
                raise AppError("invalid_test_profile", f"第 {i} 行选择了未配置的测试 profile")
            seen.add(key)
            tasks.append({**item, "repository_id": repo_id, "repository_name": repo["name"],
                          "source_snapshot_hash": repo["tree_hash"], "test_profile_id": profile,
                          "language": item.get("language", "python")})
        digest = hashlib.sha256(raw).hexdigest()
        value = dict(id=uid("ds_"), name=name, sha256=digest, task_count=len(tasks),
                     created_at=now(), tasks=tasks)
        await self.db.put("dataset", value)
        return value
