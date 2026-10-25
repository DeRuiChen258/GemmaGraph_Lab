import asyncio

import pytest
from gemmagraph.agent.budgets import record_model_reply
from gemmagraph.agent.nodes.verify_patch import verify_patch
from gemmagraph.agent.runtime import execute


def test_unknown_runtime_tokens_remain_unknown_across_calls():
    first = record_model_reply({"model_calls": 0, "input_tokens": None}, {
        "provider": "llama_cpp_local", "input_tokens": 10, "output_tokens": None})
    assert first["input_tokens"] == 10 and first["output_tokens"] is None
    assert first["token_count_mode"] == "runtime_usage_or_unknown"
    second = record_model_reply(first, {"provider": "llama_cpp_local", "input_tokens": None,
                                       "output_tokens": 5})
    third = record_model_reply(second, {"input_tokens": 10, "output_tokens": 5})
    assert second["model_calls"] == 2 and third["model_calls"] == 3
    assert third["input_tokens"] is None and third["output_tokens"] is None


async def test_resume_recovery_applies_pending_decision_only_once(workflow):
    w = workflow
    assert await execute(w.run, w.deps) == "awaiting_review"
    pending = await w.db.get("run", w.run["id"])
    assert pending["outcome"] == "verified"
    decision = {"review_id": pending["review"]["review_id"],
                "patch_hash": pending["review"]["patch_hash"], "decision": "accept"}
    assert await execute(w.run, w.deps, resume=decision, continue_saved=True) == "completed"
    assert await execute(w.run, w.deps, resume=decision, continue_saved=True) == "completed"
    assert w.model.calls == 2


async def test_resume_worker_recovers_running_resume_job(workflow, monkeypatch):
    from gemmagraph import worker
    w = workflow
    await w.db.update("run", w.run["id"], status="running")
    calls = []
    async def execute_fixture(run, deps, **kwargs):
        calls.append(kwargs)
        return "completed"
    monkeypatch.setattr(worker, "execute", execute_fixture)
    decision = {"decision": "accept"}
    job = {"id": "job_fixture", "kind": "resume", "resource_id": "resume_resource",
           "attempts": 1, "payload": {"run_id": w.run["id"], "resume": decision}}
    await worker.execute_one(job, "owner_fixture", w.db, None, w.deps, asyncio.Event())
    assert calls == [{"resume": decision, "continue_saved": True}]


@pytest.mark.parametrize("baseline", [
    {"exit_code": 2, "collected": 1, "timed_out": False},
    {"exit_code": 1, "collected": 0, "timed_out": False},
    {"exit_code": 1, "collected": 1, "timed_out": True},
    {"exit_code": 1, "collected": 1, "environment_error": True},
])
async def test_environment_errors_and_empty_baselines_cannot_prove_repair(workflow, baseline):
    w = workflow
    w.sandbox.results = [0]
    result = await verify_patch({"run_id": w.run["id"], "workspace_ref": str(w.source),
                                "config_snapshot": w.run["config_snapshot"], "attempt": 1,
                                "baseline_result_ref": baseline}, w.deps)
    assert result["outcome"] == "unverified"
    assert not result["verification_ref"]["baseline_reproduced"]
