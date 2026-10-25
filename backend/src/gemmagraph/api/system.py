import time
from datetime import datetime
from math import isfinite

from fastapi import APIRouter, Request

from gemmagraph.agent.graph import NODES
from gemmagraph.errors import AppError
from gemmagraph.providers.factory import provider_factory

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(request: Request):
    db = request.app.state.db
    try:
        worker = await db.get("worker", "active")
        age = time.time() - datetime.fromisoformat(worker["updated_at"]).timestamp()
    except AppError:
        worker, age = {}, float("inf")
    return {"status": "ok" if age < 12 else "degraded",
            "worker": {"alive": age < 12, "last_seen_seconds": round(age, 1) if isfinite(age) else None},
            "database": "ready"}


@router.get("/overview")
async def overview(request: Request):
    db = request.app.state.db
    repos, runs, experiments = await db.list("repository"), await db.list("run"), await db.list("experiment")
    return {"repositories": len(repos), "runs": len(runs),
            "by_status": {status: sum(r["status"] == status for r in runs)
                          for status in ("queued", "running", "awaiting_review", "completed", "blocked", "failed")},
            "experiments": len(experiments),
            "recent_runs": sorted(runs, key=lambda r: r["created_at"], reverse=True)[:8],
            "model": request.app.state.settings.model_status(),
            "sandbox": await sandbox_status(request.app.state.sandbox)}


async def sandbox_status(sandbox):
    try:
        return {"available": True, "engine_version": await sandbox.available()}
    except Exception as e:
        return {"available": False, "reason": str(e)[:300]}


@router.get("/providers/status")
async def provider_status(request: Request):
    settings = request.app.state.settings
    return {**settings.model_status(), "capabilities": {
        "generation": "unknown", "streaming": "not_probed",
        "json_schema": "not_probed", "token_count": "unknown", "seed": "unknown"}}


@router.post("/providers/check")
async def provider_check(request: Request):
    return await provider_factory(request.app.state.settings).check()


@router.get("/settings")
async def get_settings(request: Request):
    try:
        overrides = await request.app.state.db.get("setting", "defaults")
    except AppError:
        overrides = {}
    return {"defaults": {**request.app.state.settings.defaults(), **overrides.get("defaults", {})},
            "profiles": [{"id": key, "command": value["command"], "memory_mb": value["memory_mb"],
                          "timeout_seconds": 120} for key, value in request.app.state.settings.profiles().items()],
            "model": request.app.state.settings.model_status(),
            "sandbox": await sandbox_status(request.app.state.sandbox)}


@router.patch("/settings")
async def patch_settings(payload: dict, request: Request):
    if set(payload) - {"defaults"}:
        raise AppError("invalid_setting", "仅能修改非敏感的默认预算")
    values = payload.get("defaults", {})
    current = request.app.state.settings.defaults()
    if set(values) - set(current):
        raise AppError("invalid_setting", "包含未知默认参数")
    for key in ("max_attempts", "max_model_calls", "active_timeout_seconds", "test_timeout_seconds",
                "evidence_tokens", "max_changed_files", "graph_hops", "max_candidates", "seed_count"):
        if key in values and (not isinstance(values[key], int) or values[key] < 1):
            raise AppError("invalid_setting", f"{key} 必须为正整数")
    await request.app.state.db.put("setting", {"id": "defaults", "defaults": values})
    return {"defaults": {**current, **values}}


@router.get("/workflow")
def workflow():
    return {"version": 1, "nodes": [{"id": n, "label": n.replace("_", " ")} for n in NODES],
            "edges": [{"source": a, "target": b} for a, b in [
                ("START", "validate_task"), ("validate_task", "prepare_workspace"),
                ("validate_task", "finalize"), ("prepare_workspace", "index_repository"),
                ("index_repository", "collect_baseline"), ("collect_baseline", "retrieve_context"),
                ("retrieve_context", "plan_fix"), ("plan_fix", "generate_patch"),
                ("generate_patch", "validate_patch"), ("validate_patch", "apply_patch"),
                ("validate_patch", "reflect"), ("apply_patch", "verify_patch"),
                ("verify_patch", "human_review"), ("verify_patch", "reflect"),
                ("reflect", "retrieve_context"), ("reflect", "plan_fix"),
                ("reflect", "generate_patch"), ("reflect", "human_review"),
                ("human_review", "retrieve_context"), ("human_review", "finalize"),
                ("finalize", "END")] ]}
