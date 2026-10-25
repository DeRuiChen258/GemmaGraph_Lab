from gemmagraph.services.workspaces import tree_hash


async def prepare_workspace(state, deps):
    root = deps.workspaces.reset(state["run_id"], state["source_snapshot"])
    await deps.artifacts.write(state["run_id"], "source-manifest.json", {
        "snapshot_id": state["source_snapshot"], "tree_hash": state["repository"]["tree_hash"],
        "workspace_tree_hash": tree_hash(root),
    }, "application/json")
    return {"workspace_ref": str(root)}
