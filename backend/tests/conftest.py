"""Offline workflow fixtures: canned model/test replies are protocol fixtures only.

These fixtures exercise real LangGraph scheduling, checkpoints, SQLite records,
AST indexing and patch application. They do not establish real inference or
container execution results.
"""

import asyncio
import json
import os
import selectors
from types import SimpleNamespace

import pytest
from gemmagraph.agent.runtime import AgentDeps
from gemmagraph.codegraph.store import IndexStore
from gemmagraph.contracts import RunCreate
from gemmagraph.db import Database
from gemmagraph.event_store import EventStore
from gemmagraph.sandbox.docker_runner import DockerRunner
from gemmagraph.services.artifacts import Artifacts
from gemmagraph.services.runs import Runs
from gemmagraph.services.workspaces import Workspaces, tree_hash
from gemmagraph.settings import Settings
from langgraph.checkpoint.memory import InMemorySaver

# Only enable in a sandbox that denies writes to asyncio's self-pipe. A bounded
# selector wait also lets thread callbacks finish during Runner.close(), after
# all ordinary coroutine tasks have been cancelled.
if os.environ.get("GEMMAGRAPH_TEST_POLL_LOOP") == "1":
    class PollingSelector(selectors.DefaultSelector):
        def select(self, timeout=None):
            return super().select(.01 if timeout is None else min(timeout, .01))

    class PollingPolicy(asyncio.DefaultEventLoopPolicy):
        def new_event_loop(self):
            return asyncio.SelectorEventLoop(PollingSelector())

    asyncio.set_event_loop_policy(PollingPolicy())

SOURCE = "def add(left, right):\n    return left - right\n"
PATCH = "--- a/src/calc.py\n+++ b/src/calc.py\n@@ -1,2 +1,2 @@\n def add(left, right):\n-    return left - right\n+    return left + right\n"
PLAN = json.dumps({"summary": "Correct addition to use the plus operator.",
                   "files": ["src/calc.py"], "evidence_ids": [], "validation": ["pytest"]})
REFLECT = json.dumps({"failure_type": "test_failure", "evidence_gap": "",
                     "next_step": "regenerate", "summary": "Try another candidate patch."})


class ProtocolModel:
    def __init__(self):
        self.replies = [PLAN, PATCH]
        self.calls = 0

    async def check(self):
        return {"reachable": True, "protocol_fixture": True}

    async def generate(self, prompt, seed=None):
        reply = self.replies[self.calls]
        self.calls += 1
        return {"text": reply, "input_tokens": 10, "output_tokens": 5}


class ProtocolSandbox(DockerRunner):
    def __init__(self, settings):
        super().__init__(settings)
        self.calls = 0
        self.results = [1, 0]

    async def available(self):
        return "protocol_fixture"

    async def run(self, root, profile_id, timeout):
        exit_code = self.results[self.calls]
        self.calls += 1
        return {"exit_code": exit_code, "timed_out": False, "collected": 1,
                "stdout": "fixture: no repository code was executed", "stderr": "",
                "environment_error": False}


@pytest.fixture
async def workflow(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path / "data")
    workspaces = Workspaces(settings)
    source = workspaces.source("snapshot_fixture")
    (source / "src").mkdir(parents=True)
    (source / "src/calc.py").write_text(SOURCE)
    repository = {"id": "repo_fixture", "name": "protocol fixture",
                  "snapshot_id": "snapshot_fixture", "tree_hash": tree_hash(source)}
    db = await Database(settings.data_dir / "app.sqlite3").open()
    try:
        events = EventStore(db)
        artifacts = Artifacts(db, settings)
        runs = Runs(db, settings, workspaces, events)
        await db.put("repository", repository)
        run = runs.prepare(repository, RunCreate(repository_id=repository["id"], issue="Fix add subtraction bug"))
        await db.put("run", run)
        run["repository"] = repository
        model = ProtocolModel()
        sandbox = ProtocolSandbox(settings)
        deps = AgentDeps(db, events, artifacts, workspaces, IndexStore(settings, workspaces),
                         lambda: model, sandbox, settings, InMemorySaver())
        yield SimpleNamespace(run=run, deps=deps, model=model, sandbox=sandbox, source=source,
                              db=db, events=events, artifacts=artifacts)
    finally:
        await db.close()
