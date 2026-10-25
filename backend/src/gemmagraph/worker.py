import asyncio
import fcntl
import signal
from uuid import uuid4

from gemmagraph.agent.runtime import AgentDeps, execute
from gemmagraph.codegraph.store import IndexStore
from gemmagraph.db import Database, now
from gemmagraph.event_store import EventStore
from gemmagraph.providers.factory import provider_factory
from gemmagraph.queue import Queue
from gemmagraph.sandbox.docker_runner import DockerRunner
from gemmagraph.services.artifacts import Artifacts
from gemmagraph.services.experiments import Experiments
from gemmagraph.services.runs import Runs
from gemmagraph.services.workspaces import Workspaces
from gemmagraph.settings import Settings


async def heartbeat(db, worker_id, stop):
    while not stop.is_set():
        await db.put("worker", {"id": "active", "worker_id": worker_id, "updated_at": now()})
        try:
            await asyncio.wait_for(stop.wait(), timeout=4)
        except asyncio.TimeoutError:
            pass


async def execute_one(job, owner, db, queue, deps, shutdown):
    lease_stop = asyncio.Event()
    task = watcher = None
    async def renew():
        while not lease_stop.is_set():
            try:
                await asyncio.wait_for(lease_stop.wait(), timeout=8)
            except asyncio.TimeoutError:
                await queue.renew(job["id"], owner)
    renewal = asyncio.create_task(renew())
    try:
        if job["kind"] == "index":
            repository = await db.get("repository", job["resource_id"])
            await asyncio.to_thread(deps.index_store.load_or_build, repository)
            await db.update("repository", repository["id"], index_status="ready")
            return
        run_id = job["payload"].get("run_id", job["resource_id"])
        run = await db.get("run", run_id)
        if run.get("cancel_requested") and run["status"] in {"queued", "running"}:
            try:
                await deps.sandbox.stop_run(run_id)
            except Exception:
                pass
            await db.update("run", run_id, status="cancelled", current_node=None,
                            outcome="cancelled", summary="运行在启动前已取消")
            await deps.events.append(run_id, "run.cancelled", source_key="run:cancelled")
            return
        run["repository"] = await db.get("repository", run["repository_id"])
        if job["kind"] == "resume":
            if run.get("status") not in {"queued", "running"}:
                return
            if run["status"] == "running":
                await deps.events.append(run_id, "run.recovered", source_key=f"run:recovered:{job['attempts'] + 1}")
                task = asyncio.create_task(execute(run, deps, resume=job["payload"]["resume"],
                                                 continue_saved=True))
            else:
                await db.update("run", run_id, status="running", current_node="human_review")
                task = asyncio.create_task(execute(run, deps, job["payload"]["resume"]))
        else:
            if run.get("status") not in {"queued", "running"}:
                return
            recovered = run.get("status") == "running"
            if not recovered:
                await db.update("run", run_id, status="running", current_node="validate_task")
                await deps.events.append(run_id, "run.started", source_key="run:started")
                task = asyncio.create_task(execute(run, deps))
            else:
                await deps.events.append(run_id, "run.recovered", source_key=f"run:recovered:{job['attempts'] + 1}")
                task = asyncio.create_task(execute(run, deps, continue_saved=True))

        async def wait_control():
            while not task.done():
                current = await db.get("run", run_id)
                if current.get("cancel_requested"):
                    task.cancel()
                    return "cancel"
                if shutdown.is_set():
                    task.cancel()
                    return "shutdown"
                await asyncio.sleep(.75)

        watcher = asyncio.create_task(wait_control())
        done, _ = await asyncio.wait({task, watcher}, return_when=asyncio.FIRST_COMPLETED)
        control = watcher.result() if watcher in done else None
        if control == "shutdown":
            await asyncio.gather(task, return_exceptions=True)
            return "shutdown"
        if control == "cancel":
            await asyncio.gather(task, return_exceptions=True)
            await db.update("run", run_id, status="cancelled", current_node=None,
                            outcome="cancelled", summary="运行已取消")
            await deps.events.append(run_id, "run.cancelled", source_key="run:cancelled")
        else:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
            result = await task
            await deps.events.append(run_id, "run." + result, source_key=f"run:terminal:{result}")
            if run.get("experiment_id"):
                await deps.experiments.detail(run["experiment_id"])
    finally:
        outstanding = [pending for pending in (watcher, task) if pending is not None and not pending.done()]
        for pending in outstanding:
            pending.cancel()
        await asyncio.gather(*outstanding, return_exceptions=True)
        lease_stop.set()
        renewal.cancel()
        await asyncio.gather(renewal, return_exceptions=True)


async def run_worker():
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = settings.data_dir / "worker.lock"
    lock_file = lock_path.open("w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as e:
        raise SystemExit("A GemmaGraph worker already holds this data directory") from e
    db = await Database(settings.data_dir / "app.sqlite3").open()
    events, queue = EventStore(db), Queue(db)
    workspaces = Workspaces(settings)
    artifacts = Artifacts(db, settings)
    indexes = IndexStore(settings, workspaces)
    runs = Runs(db, settings, workspaces, events)
    experiments = Experiments(db, settings, workspaces, runs)
    async with AsyncSqliteSaver.from_conn_string(str(settings.data_dir / "checkpoints.sqlite3")) as cp:
        await cp.setup()
        deps = AgentDeps(db, events, artifacts, workspaces, indexes,
                         lambda: provider_factory(settings), DockerRunner(settings), settings, cp, experiments)
        owner = uuid4().hex
        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        pulse = asyncio.create_task(heartbeat(db, owner, stop))
        try:
            while not stop.is_set():
                job = await queue.claim(owner)
                if not job:
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=.8)
                    except asyncio.TimeoutError:
                        continue
                    break
                try:
                    result = await execute_one(job, owner, db, queue, deps, stop)
                    if result == "shutdown":
                        await queue.release(job["id"], owner)
                        break
                    await queue.finish(job["id"], owner)
                except asyncio.CancelledError:
                    await queue.finish(job["id"], owner, "cancelled")
                    raise
                except Exception as e:
                    if job["kind"] in {"run", "resume"}:
                        run_id = job["payload"].get("run_id", job["resource_id"])
                        try:
                            run = await db.get("run", run_id)
                            await db.update("run", run_id, status="failed", current_node=None,
                                            outcome="failed", error={"code": getattr(e, "code", "execution_error"),
                                                                     "message": str(e)[:800]})
                            await events.append(run_id, "run.failed", {"message": str(e)[:500]},
                                                source_key=f"run:failed:{job['id']}")
                            if run.get("experiment_id"):
                                await experiments.detail(run["experiment_id"])
                        except Exception:
                            pass
                    elif job["kind"] == "index":
                        await db.update("repository", job["resource_id"], index_status="failed",
                                         diagnostics=[{"reason": str(e)[:500]}])
                    await queue.finish(job["id"], owner, "failed")
        finally:
            stop.set()
            pulse.cancel()
            await asyncio.gather(pulse, return_exceptions=True)
            await db.close()
            lock_file.close()


def serve():
    asyncio.run(run_worker())
