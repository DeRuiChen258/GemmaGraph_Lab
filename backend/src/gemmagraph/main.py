from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gemmagraph.api import artifacts, datasets, experiments, repositories, runs, system
from gemmagraph.codegraph.store import IndexStore
from gemmagraph.db import Database
from gemmagraph.errors import AppError
from gemmagraph.event_store import EventStore
from gemmagraph.queue import Queue
from gemmagraph.sandbox.docker_runner import DockerRunner
from gemmagraph.services.artifacts import Artifacts
from gemmagraph.services.datasets import Datasets
from gemmagraph.services.experiments import Experiments
from gemmagraph.services.repositories import Repositories
from gemmagraph.services.runs import Runs
from gemmagraph.services.workspaces import Workspaces
from gemmagraph.settings import Settings


@asynccontextmanager
async def lifespan(app):
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = await Database(settings.data_dir / "app.sqlite3").open()
    events, queue, workspaces = EventStore(db), Queue(db), Workspaces(settings)
    artifacts = Artifacts(db, settings)
    app.state.settings = settings
    app.state.db = db
    app.state.events = events
    app.state.queue = queue
    app.state.workspaces = workspaces
    app.state.index_store = IndexStore(settings, workspaces)
    app.state.artifacts = artifacts
    app.state.repositories = Repositories(db, settings, workspaces)
    app.state.datasets = Datasets(db)
    app.state.runs = Runs(db, settings, workspaces, events)
    app.state.experiments = Experiments(db, settings, workspaces, app.state.runs)
    app.state.sandbox = DockerRunner(settings)
    yield
    await db.close()


app = FastAPI(title="GemmaGraph Lab", description="Local LangGraph code-repair research workbench",
              version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=Settings().allowed_origins,
                   allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
                   allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID", "X-Request-ID"],
                   allow_credentials=False)


@app.middleware("http")
async def origin_guard(request, call_next):
    origin = request.headers.get("origin")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in Settings().allowed_origins:
        return JSONResponse(status_code=403, content={"code": "origin_forbidden",
                                                      "message": "此本地 API 不接受该来源的写入请求"})
    return await call_next(request)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    from uuid import uuid4
    return JSONResponse(status_code=exc.status,
                        content={"code": exc.code, "message": exc.message,
                                 "request_id": request.headers.get("x-request-id", uuid4().hex)})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    import logging
    from uuid import uuid4
    request_id = request.headers.get("x-request-id", uuid4().hex)
    logging.getLogger("gemmagraph.api").exception("Unhandled request error %s", request_id)
    return JSONResponse(status_code=500, content={"code": "internal_error",
                                                  "message": "服务遇到未预期错误",
                                                  "request_id": request_id})


for router in (system.router, repositories.router, runs.router, experiments.router,
               datasets.router, artifacts.router):
    app.include_router(router, prefix="/api/v1")


def serve():
    settings = Settings()
    uvicorn.run("gemmagraph.main:app", host=settings.api_host, port=settings.api_port,
                log_level="info", access_log=False)
