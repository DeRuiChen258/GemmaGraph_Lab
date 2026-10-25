from conftest import PATCH, PLAN, REFLECT, SOURCE
from gemmagraph.agent.runtime import execute


async def test_real_graph_interrupt_resume_persists_patch_and_keeps_snapshot(workflow):
    w = workflow
    assert await execute(w.run, w.deps) == "awaiting_review"
    pending = await w.db.get("run", w.run["id"])
    assert pending["attempt"] == 1
    assert pending["verification"]["outcome"] == "verified"
    assert pending["baseline"]["exit_code"] == 1
    assert pending["patch"]["sha256"] == pending["review"]["patch_hash"]
    assert pending["evidence"] and pending["plan"]
    assert (w.source / "src/calc.py").read_text() == SOURCE
    assert (w.deps.workspaces.workspace(w.run["id"]) / "src/calc.py").read_text().endswith("return left + right\n")
    decision = {"review_id": pending["review"]["review_id"],
                "patch_hash": pending["review"]["patch_hash"], "decision": "accept"}
    assert await execute(w.run, w.deps, resume=decision) == "completed"
    complete = await w.db.get("run", w.run["id"])
    assert complete["outcome"] == "verified"
    assert complete["review_status"] == "accept"
    assert w.model.calls == 2 and w.sandbox.calls == 2
    events = await w.events.read(w.run["id"])
    assert not any(e["type"] == "node.failed" for e in events)
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))


async def test_rejection_completes_and_recovery_does_not_repeat_model_calls(workflow):
    w = workflow
    assert await execute(w.run, w.deps) == "awaiting_review"
    assert await execute(w.run, w.deps, continue_saved=True) == "awaiting_review"
    assert w.model.calls == 2
    pending = await w.db.get("run", w.run["id"])
    decision = {"review_id": pending["review"]["review_id"],
                "patch_hash": pending["review"]["patch_hash"], "decision": "reject"}
    assert await execute(w.run, w.deps, resume=decision) == "completed"
    complete = await w.db.get("run", w.run["id"])
    assert complete["outcome"] == "rejected"


async def test_human_revision_runs_a_new_attempt(workflow):
    w = workflow
    w.model.replies += [PLAN, PATCH]
    w.sandbox.results += [0]
    assert await execute(w.run, w.deps) == "awaiting_review"
    pending = await w.db.get("run", w.run["id"])
    decision = {"review_id": pending["review"]["review_id"],
                "patch_hash": pending["review"]["patch_hash"], "decision": "revise",
                "feedback": "Review the addition operator once more."}
    assert await execute(w.run, w.deps, resume=decision) == "awaiting_review"
    revised = await w.db.get("run", w.run["id"])
    assert revised["attempt"] == 2
    assert revised["review"]["review_id"] != pending["review"]["review_id"]
    assert w.model.calls == 4


async def test_failed_verification_can_reflect_and_retry(workflow):
    w = workflow
    w.run["review_policy"] = "deferred"
    w.model.replies = [PLAN, PATCH, REFLECT, PATCH]
    w.sandbox.results = [1, 1, 0]
    assert await execute(w.run, w.deps) == "completed"
    complete = await w.db.get("run", w.run["id"])
    assert complete["outcome"] == "verified"
    assert complete["attempt"] == 2
    assert w.model.calls == 4 and w.sandbox.calls == 3


async def test_preflight_failure_finalizes_without_model_generation(workflow, monkeypatch):
    w = workflow
    async def unavailable():
        raise RuntimeError("fixture Docker unavailable")
    monkeypatch.setattr(w.sandbox, "available", unavailable)
    assert await execute(w.run, w.deps) == "blocked"
    blocked = await w.db.get("run", w.run["id"])
    assert blocked["error"]["code"] == "preflight_blocked"
    assert w.model.calls == 0 and w.sandbox.calls == 0


async def test_exhausted_model_budget_reaches_review_without_excess_call(workflow):
    w = workflow
    w.run["config_snapshot"]["budget"]["max_model_calls"] = 2
    w.sandbox.results = [1, 1]
    assert await execute(w.run, w.deps) == "awaiting_review"
    assert w.model.calls == 2
