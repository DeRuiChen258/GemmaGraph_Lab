import asyncio
import json

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from gemmagraph.contracts import ReviewDecision, RunCreate
from gemmagraph.errors import AppError
from gemmagraph.services.runs import editable_python_files

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", status_code=202)
async def create_run(body: RunCreate, request: Request,
                     idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=200)):
    repo = await request.app.state.db.get("repository", body.repository_id)
    defaults = await request.app.state.db.list("setting")
    saved = next((x.get("defaults", {}) for x in defaults if x["id"] == "defaults"), {})
    if "budget" not in body.model_fields_set and saved:
        from gemmagraph.contracts import Budget
        budget_values = {key: value for key, value in saved.items() if key in Budget.model_fields}
        body = body.model_copy(update={"budget": Budget.model_validate({**body.budget.model_dump(), **budget_values})})
    if body.test_profile_id not in request.app.state.settings.profiles():
        raise AppError("invalid_test_profile", "未知的测试 profile")
    allowed = editable_python_files(request.app.state.workspaces.source(repo["snapshot_id"]))
    if not allowed:
        raise AppError("no_editable_python", "仓库中没有可修改的 Python 文件")
    return await request.app.state.runs.create(body.repository_id, body, idempotency_key)


@router.get("")
async def list_runs(request: Request, status: str | None = None, repository_id: str | None = None,
                    limit: int = Query(50, ge=1, le=200)):
    values = sorted(await request.app.state.db.list("run"), key=lambda r: r["created_at"], reverse=True)
    values = [r for r in values if (not status or r["status"] == status)
              and (not repository_id or r["repository_id"] == repository_id)]
    return {"items": values[:limit], "next_cursor": values[limit]["id"] if len(values) > limit else None}


@router.get("/{run_id}")
async def get_run(run_id: str, request: Request):
    return await request.app.state.db.get("run", run_id)


@router.get("/{run_id}/events/history")
async def event_history(run_id: str, request: Request, after_seq: int = Query(0, ge=0),
                        limit: int = Query(500, ge=1, le=500)):
    await request.app.state.db.get("run", run_id)
    items = await request.app.state.events.read(run_id, after_seq, limit)
    return {"items": items, "next_seq": (items[-1]["seq"] + 1) if items else after_seq + 1}


@router.get("/{run_id}/events")
async def events(run_id: str, request: Request, after_seq: int = Query(0, ge=0),
                 last_event_id: str | None = Header(None, alias="Last-Event-ID")):
    await request.app.state.db.get("run", run_id)
    if last_event_id and last_event_id.isdigit():
        after_seq = max(after_seq, int(last_event_id))
    event_store, db = request.app.state.events, request.app.state.db

    async def stream():
        cursor, sent = after_seq, 0
        while sent < 10000:
            rows = await event_store.read(run_id, cursor, limit=100)
            for value in rows:
                cursor, sent = value["seq"], sent + 1
                yield f"id: {cursor}\nevent: {value['type']}\ndata: {json.dumps(value, ensure_ascii=False)}\n\n"
            run = await db.get("run", run_id)
            if run["status"] in {"awaiting_review", "completed", "blocked", "failed", "cancelled"} and not rows:
                return
            if not rows:
                try:
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    return
            if await request.is_disconnected():
                return
            yield ": heartbeat\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@router.post("/{run_id}/cancel", status_code=202)
async def cancel_run(run_id: str, request: Request):
    run = await request.app.state.db.get("run", run_id)
    if run["status"] in {"completed", "blocked", "failed", "cancelled"}:
        return run
    value = await request.app.state.db.update("run", run_id, cancel_requested=True)
    await request.app.state.events.append(run_id, "run.cancel_requested", source_key="run:cancel-requested")
    return value


@router.post("/{run_id}/resume", status_code=202)
async def resume_run(run_id: str, body: ReviewDecision, request: Request,
                     idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=200)):
    return await request.app.state.runs.resume(run_id, body, idempotency_key)


@router.get("/{run_id}/artifacts")
async def list_artifacts(run_id: str, request: Request):
    await request.app.state.db.get("run", run_id)
    return {"items": await request.app.state.artifacts.list(run_id)}
