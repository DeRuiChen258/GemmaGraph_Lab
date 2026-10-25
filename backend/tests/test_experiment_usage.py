"""Unknown model usage must survive aggregation instead of becoming zero."""

from gemmagraph.services.experiments import Experiments


async def test_unknown_usage_is_preserved_in_experiment_metrics(workflow):
    w = workflow
    first = await w.db.get("run", w.run["id"])
    first.update(status="completed", outcome="verified", usage={"input_tokens": 20,
                 "output_tokens": None, "thought_tokens": None, "active_seconds": 1})
    second = {**first, "id": "run_second", "usage": {"input_tokens": 10, "output_tokens": 5,
              "thought_tokens": 0, "active_seconds": 2}}
    await w.db.put("run", first)
    await w.db.put("run", second)
    await w.db.put("experiment", {"id": "exp_fixture", "run_ids": [first["id"], second["id"]]})
    experiments = Experiments(w.db, w.deps.settings, w.deps.workspaces, None)
    result = await experiments.detail("exp_fixture")
    metric = result["metrics"][0]
    assert metric["input_tokens"] == 30
    assert metric["output_tokens"] is None and metric["thought_tokens"] is None
    assert metric["activity_seconds"] == 3
    assert metric["solve_rate"] == 1
