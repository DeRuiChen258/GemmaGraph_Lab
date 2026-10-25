from gemmagraph.sandbox.patches import validate


async def validate_patch(state, deps):
    run = await deps.db.get("run", state["run_id"])
    result = validate(state.get("patch_text", ""), run.get("config_snapshot", {}).get(
        "allowed_paths", ["src/"]), state["config_snapshot"]["budget"]["max_changed_files"])
    return {"patch_validation": result, "error": None if result["valid"] else {
        "code": "invalid_patch", "message": result["message"]}}


def route_patch_validated(state):
    if state.get("outcome") == "unverified":
        return "human_review" if state.get("patch_ref") else "finalize"
    return "apply_patch" if (state.get("patch_validation") or {}).get("valid") else "reflect"
