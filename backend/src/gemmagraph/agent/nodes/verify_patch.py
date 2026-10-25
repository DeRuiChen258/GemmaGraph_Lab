from pathlib import Path


async def verify_patch(state, deps):
    result = await deps.sandbox.run(Path(state["workspace_ref"]), state["config_snapshot"]["test_profile_id"],
                                    state["config_snapshot"]["budget"]["test_timeout_seconds"])
    artifact = await deps.artifacts.write(state["run_id"], f"verification-{state['attempt']}.json",
                                          result, "application/json")
    baseline = state.get("baseline_result_ref") or {}
    reproduced = (baseline.get("exit_code") == 1 and baseline.get("collected", 0) > 0
                  and not baseline.get("timed_out") and not baseline.get("environment_error"))
    passed = result.get("exit_code") == 0 and not result.get("timed_out") and result.get("collected", 0) > 0
    if baseline.get("environment_error") or result.get("environment_error"):
        outcome = "unverified"
    else:
        outcome = "verified" if reproduced and passed else "unverified"
    verification = {**result, "artifact_id": artifact["id"], "baseline_reproduced": reproduced,
                    "tests_passed": passed, "outcome": outcome}
    await deps.events.append(state["run_id"], "verification.completed", verification,
                             node="verify_patch", attempt=state["attempt"],
                             source_key=f"verification:{state['attempt']}:{artifact['sha256']}")
    return {"verification_ref": verification, "outcome": outcome}


def route_verification(state):
    return "human_review" if state.get("outcome") == "verified" else "reflect"
