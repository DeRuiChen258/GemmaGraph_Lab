from pathlib import Path


async def collect_baseline(state, deps):
    root = Path(state["workspace_ref"])
    result = await deps.sandbox.run(root, state["config_snapshot"]["test_profile_id"],
                                    state["config_snapshot"]["budget"]["test_timeout_seconds"])
    artifact = await deps.artifacts.write(state["run_id"], "baseline-test.json", result,
                                          "application/json")
    result["artifact_id"] = artifact["id"]
    return {"baseline_result_ref": result}
