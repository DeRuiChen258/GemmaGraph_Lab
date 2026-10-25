import asyncio

from gemmagraph.codegraph.retrieval import retrieve


async def retrieve_context(state, deps):
    config = state["config_snapshot"]
    repository = state["repository"]
    index = await asyncio.to_thread(deps.index_store.load_or_build, repository)
    failure = (state.get("baseline_result_ref") or {}).get("summary", "")
    if state.get("reflection"):
        failure += " " + state["reflection"].get("evidence_gap", "")
    items = retrieve(index, state["issue"], config["method"],
                     config["budget"]["evidence_tokens"], deps.settings.defaults(), failure)
    await deps.artifacts.write(state["run_id"], f"evidence-{state.get('attempt',0)}.json", items,
                               "application/json")
    return {"evidence": items}
