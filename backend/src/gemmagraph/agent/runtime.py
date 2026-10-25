from dataclasses import dataclass

from langgraph.types import Command

from gemmagraph.agent.graph import build_graph, initial_state


@dataclass
class AgentDeps:
    db: object
    events: object
    artifacts: object
    workspaces: object
    index_store: object
    provider_factory: object
    sandbox: object
    settings: object
    checkpointer: object
    experiments: object = None


async def execute(run, deps, resume=None, continue_saved=False):
    config = {"configurable": {"thread_id": run["id"]}, "recursion_limit": 80}
    graph = build_graph(deps)
    if continue_saved:
        checkpoint = await deps.checkpointer.aget_tuple(config)
        next_input = None if checkpoint else initial_state(run)
        if checkpoint and resume:
            saved = await graph.aget_state(config)
            if any(task.interrupts for task in saved.tasks):
                next_input = Command(resume=resume)
        result = await graph.ainvoke(next_input, config=config)
    elif resume:
        result = await graph.ainvoke(Command(resume=resume), config=config)
    else:
        result = await graph.ainvoke(initial_state(run), config=config)
    if "__interrupt__" in result:
        pending = result["__interrupt__"][0].value
        await deps.db.update("run", run["id"], status="awaiting_review", current_node="human_review",
                             review=pending, review_status="pending",
                             outcome=result.get("outcome", "unverified"),
                             attempt=result.get("attempt", 0), evidence=result.get("evidence", []),
                             plan=result.get("plan"), baseline=result.get("baseline_result_ref"),
                             verification=result.get("verification_ref"), patch=result.get("patch_ref"),
                             usage=result.get("usage", {}), error=result.get("error"))
        await deps.events.append(run["id"], "review.required", pending, node="human_review",
                                 source_key=f"review:{pending['review_id']}")
        return "awaiting_review"
    outcome = result.get("outcome", "failed")
    status = "blocked" if outcome == "blocked" else (
        "completed" if outcome in {"verified", "unverified", "no_patch", "rejected"} else "failed")
    await deps.db.update("run", run["id"], status=status, current_node=None,
                         outcome=outcome, summary=result.get("summary"), attempt=result.get("attempt", 0),
                         evidence=result.get("evidence", []), plan=result.get("plan"),
                         baseline=result.get("baseline_result_ref"),
                         verification=result.get("verification_ref"), patch=result.get("patch_ref"),
                         review=result.get("review"), review_status=(result.get("review") or {}).get("status", "not_requested"),
                         usage=result.get("usage", {}), error=result.get("error"))
    return status
