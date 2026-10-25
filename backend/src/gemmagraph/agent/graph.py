import time

from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph

from gemmagraph.agent.state import AgentState
from gemmagraph.errors import AppError

NODES = ["validate_task", "prepare_workspace", "index_repository", "collect_baseline",
         "retrieve_context", "plan_fix", "generate_patch", "validate_patch", "apply_patch",
         "verify_patch", "reflect", "human_review", "finalize"]


def initial_state(run):
    return {
        "schema_version": 1, "run_id": run["id"], "thread_id": run["id"], "task_id": run["id"],
        "repository_id": run["repository_id"], "repository": run["repository"],
        "issue": run["issue"], "source_snapshot": run["repository"]["snapshot_id"],
        "config_snapshot": run["config_snapshot"], "review_policy": run.get("review_policy", "interactive"),
        "workspace_ref": "", "index_ref": "", "evidence": [], "plan": None,
        "patch_ref": None, "patch_hash": None, "attempt": 0, "baseline_result_ref": None,
        "verification_ref": None, "usage": {"model_calls": 0, "input_tokens": None,
                                                "output_tokens": None, "thought_tokens": None,
                                                "active_seconds": 0,
                                                "token_count_mode": "runtime_usage_or_unknown"},
        "reflection": None, "review": None, "outcome": "pending", "error": None, "summary": None,
    }


def build_graph(deps):
    from gemmagraph.agent import nodes

    async def wrapped(name, function, state):
        rid, attempt = state["run_id"], state.get("attempt", 0)
        await deps.events.append(rid, "node.started", node=name, attempt=attempt)
        started = time.monotonic()
        try:
            update = await function(state, deps)
        except GraphInterrupt:
            raise
        except Exception as e:
            await deps.events.append(rid, "node.failed", {"error": str(e)[:500]}, node=name,
                                     attempt=attempt)
            raise
        await deps.events.append(rid, "node.completed", node=name, attempt=attempt)
        usage = dict(update.get("usage", state.get("usage", {})))
        usage["active_seconds"] = round(usage.get("active_seconds", 0)
                                        + time.monotonic() - started, 2)
        update["usage"] = usage
        latest = await deps.db.get("run", rid)
        if latest.get("cancel_requested"):
            raise AppError("cancelled", "运行已取消", 409)
        await deps.db.update("run", rid, current_node=name)
        return update

    builder = StateGraph(AgentState)
    def make_node(name, function):
        async def node(state: AgentState):
            return await wrapped(name, function, state)
        return node

    for name in NODES:
        function = getattr(nodes, name)
        builder.add_node(name, make_node(name, function))
    builder.add_edge(START, "validate_task")
    builder.add_conditional_edges("validate_task", nodes.route_validated)
    builder.add_edge("prepare_workspace", "index_repository")
    builder.add_edge("index_repository", "collect_baseline")
    builder.add_edge("collect_baseline", "retrieve_context")
    builder.add_edge("retrieve_context", "plan_fix")
    builder.add_edge("plan_fix", "generate_patch")
    builder.add_edge("generate_patch", "validate_patch")
    builder.add_conditional_edges("validate_patch", nodes.route_patch_validated)
    builder.add_edge("apply_patch", "verify_patch")
    builder.add_conditional_edges("verify_patch", nodes.route_verification)
    builder.add_conditional_edges("reflect", nodes.route_reflection)
    builder.add_conditional_edges("human_review", nodes.route_review)
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=deps.checkpointer)
