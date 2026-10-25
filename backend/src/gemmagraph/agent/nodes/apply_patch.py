from gemmagraph.errors import AppError
from gemmagraph.sandbox.patches import apply


async def apply_patch(state, deps):
    root = deps.workspaces.reset(state["run_id"], state["source_snapshot"])
    patch_path, _ = await deps.artifacts.file(state["patch_ref"]["id"])
    result = await apply(root, patch_path)
    if not result["ok"]:
        raise AppError("patch_apply_failed", result["stderr"][:1000], 422)
    return {"workspace_ref": str(root), "patch_validation": {"valid": True, "message": "补丁已应用"}}
