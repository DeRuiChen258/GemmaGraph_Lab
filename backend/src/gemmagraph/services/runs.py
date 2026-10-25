import hashlib
import json

from gemmagraph.db import now, uid
from gemmagraph.errors import AppError
from gemmagraph.queue import enqueue


def editable_python_files(root):
    paths = []
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root).as_posix()
        if any(x in {"tests", "test", "benchmarks", "fixtures"} for x in p.parts):
            continue
        if p.name in {"conftest.py", "setup.py"} or rel.startswith((".github/", "vendor/")):
            continue
        paths.append(rel)
    return paths


class Runs:
    def __init__(self, db, settings, workspaces, events):
        self.db, self.settings, self.workspaces, self.events = db, settings, workspaces, events

    def prepare(self, repo, body, review_policy="interactive", experiment_id=None):
        value = body.model_dump() if hasattr(body, "model_dump") else dict(body)
        budget = value.get("budget") or self.settings.defaults()
        if budget["evidence_tokens"] >= self.settings.model_context_window:
            raise AppError("budget_exceeds_context", "证据预算必须小于已配置的模型上下文长度")
        allowed = editable_python_files(self.workspaces.source(repo["snapshot_id"]))
        if not allowed:
            raise AppError("no_editable_python", "仓库中没有可修改的 Python 源文件")
        run_id = uid("run_")
        created = now()
        return dict(
            id=run_id, repository_id=repo["id"], repository_name=repo["name"],
            issue=value["issue"], status="queued", outcome="pending", method=value["method"],
            current_node="validate_task", attempt=0, created_at=created, updated_at=created,
            config_snapshot={"method": value["method"], "budget": budget,
                             "test_profile_id": value.get("test_profile_id", "python-pytest"),
                             "seed": value.get("seed", 42), "model": self.settings.model_status(),
                             "allowed_paths": allowed,
                             "prompt_version": self.prompt_hash(), "review_policy": review_policy},
            review_policy=review_policy, parent_run_id=value.get("parent_run_id"),
            usage={"model_calls": 0, "input_tokens": None, "output_tokens": None, "thought_tokens": None,
                   "token_count_mode": "provider_usage_or_unknown"},
            evidence=[], plan=None, baseline=None, verification=None, patch=None,
            review=None, review_status="not_requested", error=None, summary=None,
            cancel_requested=False, experiment_id=experiment_id,
        )

    @staticmethod
    def prompt_hash():
        from importlib.resources import files
        d = files("gemmagraph.prompts")
        h = hashlib.sha256()
        for name in ("planner.md", "patcher.md", "reflector.md"):
            h.update(d.joinpath(name).read_bytes())
        return h.hexdigest()

    async def create(self, repo_id, body, key):
        repo = await self.db.get("repository", repo_id)
        value = self.prepare(repo, body)
        payload = body.model_dump(mode="json")
        request_hash = hashlib.sha256(json.dumps({"repo": repo_id, "body": payload}, sort_keys=True,
                                                 ensure_ascii=False).encode()).hexdigest()
        async with self.db.transaction() as c:
            old = await (await c.execute(
                "SELECT request_hash,resource_id FROM idempotency_keys WHERE scope=? AND key=?",
                ("run:create", key),
            )).fetchone()
            if old:
                if old["request_hash"] != request_hash:
                    raise AppError("idempotency_conflict", "此幂等键已用于其他请求", 409)
                value = json.loads((await (await c.execute(
                    "SELECT data FROM resources WHERE kind='run' AND id=?", (old["resource_id"],)
                )).fetchone())[0])
                return value
            await c.execute("INSERT INTO resources VALUES('run',?,?)",
                            (value["id"], json.dumps(value, ensure_ascii=False)))
            await enqueue(c, "run", value["id"])
            await c.execute("INSERT INTO idempotency_keys VALUES(?,?,?,?)",
                            ("run:create", key, request_hash, value["id"]))
        await self.events.append(value["id"], "run.queued", {"run_id": value["id"]},
                                 source_key="run:queued")
        return value

    async def resume(self, run_id, body, key):
        from gemmagraph.contracts import ReviewDecision
        run = await self.db.get("run", run_id)
        decision = body if isinstance(body, ReviewDecision) else ReviewDecision.model_validate(body)
        prior = run.get("last_review_decision")
        digest = hashlib.sha256(decision.model_dump_json().encode()).hexdigest()
        if prior and prior.get("key") == key:
            if prior["digest"] != digest:
                raise AppError("idempotency_conflict", "此幂等键已用于其他审查决策", 409)
            return run
        pending = run.get("review") or {}
        if run.get("status") != "awaiting_review" or not pending:
            raise AppError("run_not_waiting", "运行当前未等待人工审查", 409)
        if pending.get("review_id") != decision.review_id or pending.get("patch_hash") != decision.patch_hash:
            raise AppError("stale_review", "审查请求对应的补丁已过期", 409)
        resume_value = {**decision.model_dump(), "decision": decision.decision}
        async with self.db.transaction() as c:
            current = await (await c.execute("SELECT data FROM resources WHERE kind='run' AND id=?",
                                             (run_id,))).fetchone()
            run = json.loads(current[0])
            if run.get("status") != "awaiting_review":
                raise AppError("run_busy", "运行已经恢复或状态已改变", 409)
            await c.execute("UPDATE resources SET data=? WHERE kind='run' AND id=?",
                            (json.dumps({**run, "status": "queued", "review_decision": resume_value,
                                         "last_review_decision": {"key": key, "digest": digest}},
                                        ensure_ascii=False), run_id))
            await enqueue(c, "resume", f"{run_id}:{key}", {"run_id": run_id, "resume": resume_value})
            await c.execute("INSERT INTO idempotency_keys VALUES(?,?,?,?)",
                            (f"review:{run_id}", key, digest, run_id))
        await self.events.append(run_id, "run.resumed", {"decision": decision.decision},
                                 source_key=f"resume:{key}")
        return await self.db.get("run", run_id)
