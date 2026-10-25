import json

from gemmagraph.db import now, uid
from gemmagraph.errors import AppError
from gemmagraph.queue import enqueue


class Experiments:
    def __init__(self, db, settings, workspaces, runs):
        self.db, self.settings, self.workspaces, self.runs = db, settings, workspaces, runs

    async def create(self, body, key):
        dataset = await self.db.get("dataset", body.dataset_id)
        combinations = [(task, method, seed) for task in dataset["tasks"]
                        for method in body.arms for seed in body.seeds]
        if not combinations or len(combinations) > 300:
            raise AppError("experiment_too_large", "每个实验最多包含 300 个 run")
        experiment_id = uid("exp_")
        cfg = {"arms": body.arms, "seeds": body.seeds,
               "budget": body.budget.model_dump(), "dataset_hash": dataset["sha256"],
               "planned_runs": len(combinations), "review_policy": "deferred"}
        experiment = dict(id=experiment_id, name=body.name, dataset_id=dataset["id"],
                          status="queued", created_at=now(), config=cfg,
                          run_ids=[], metrics=[], export_id=None, error_counts={})
        runs = []
        for task, method, seed in combinations:
            repo = await self.db.get("repository", task["repository_id"])
            run = self.runs.prepare(repo, {"issue": task["issue"], "method": method,
                                           "seed": seed, "budget": body.budget.model_dump(),
                                           "test_profile_id": task["test_profile_id"]},
                                    review_policy="deferred", experiment_id=experiment_id)
            run["parent_task_id"] = task["instance_id"]
            run["split"] = task.get("split")
            runs.append(run)
            experiment["run_ids"].append(run["id"])
        async with self.db.transaction() as c:
            existing = await (await c.execute(
                "SELECT request_hash,resource_id FROM idempotency_keys WHERE scope='experiment:create' AND key=?",
                (key,),
            )).fetchone()
            if existing:
                stored_hash = __import__("hashlib").sha256(body.model_dump_json().encode()).hexdigest()
                if existing["request_hash"] != stored_hash:
                    raise AppError("idempotency_conflict", "此幂等键已用于其他实验", 409)
                row = await (await c.execute("SELECT data FROM resources WHERE kind='experiment' AND id=?",
                                             (existing["resource_id"],))).fetchone()
                return json.loads(row[0])
            await c.execute("INSERT INTO resources VALUES('experiment',?,?)",
                            (experiment_id, json.dumps(experiment, ensure_ascii=False)))
            for run in runs:
                await c.execute("INSERT INTO resources VALUES('run',?,?)",
                                (run["id"], json.dumps(run, ensure_ascii=False)))
                await enqueue(c, "run", run["id"])
            digest = __import__("hashlib").sha256(body.model_dump_json().encode()).hexdigest()
            await c.execute("INSERT INTO idempotency_keys VALUES(?,?,?,?)",
                            ("experiment:create", key, digest, experiment_id))
        return experiment

    async def detail(self, experiment_id):
        exp = await self.db.get("experiment", experiment_id)
        runs = []
        for rid in exp["run_ids"]:
            try:
                r = await self.db.get("run", rid)
                runs.append({"run_id": rid, "instance_id": r.get("parent_task_id"),
                             "method": r["method"], "seed": r["config_snapshot"].get("seed"),
                             "status": r["status"], "outcome": r["outcome"],
                             "verification": r.get("verification"), "usage": r.get("usage", {}),
                             "error": r.get("error")})
            except AppError:
                continue
        groups = {}
        for r in runs:
            item = groups.setdefault(r["method"], {"method": r["method"], "planned": 0,
                        "completed": 0, "solved": 0, "environment_errors": 0,
                        "input_tokens": 0, "output_tokens": 0, "thought_tokens": 0,
                        "activity_seconds": 0,
                        "items": []})
            item["planned"] += 1
            item["completed"] += r["status"] in {"completed", "failed", "blocked", "cancelled"}
            item["solved"] += r["outcome"] == "verified"
            item["environment_errors"] += bool((r.get("verification") or {}).get("environment_error"))
            for field in ("input_tokens", "output_tokens", "thought_tokens"):
                measured = r["usage"].get(field)
                item[field] = (item[field] + measured
                               if item[field] is not None and measured is not None else None)
            item["activity_seconds"] += r["usage"].get("active_seconds", 0)
            item["items"].append(r)
        metrics = [{**v, "solve_rate": v["solved"] / v["planned"] if v["planned"] else None}
                   for v in groups.values()]
        exp["status"] = "running" if any(r["status"] in {"queued", "running", "awaiting_review"}
                                           for r in runs) else "completed"
        exp["metrics"], exp["runs"] = metrics, runs
        await self.db.update("experiment", experiment_id, status=exp["status"], metrics=metrics)
        return exp
