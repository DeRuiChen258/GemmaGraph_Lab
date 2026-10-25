import asyncio


async def index_repository(state, deps):
    index = await asyncio.to_thread(deps.index_store.load_or_build, state["repository"])
    await deps.db.update("repository", state["repository_id"], index_status="ready",
                         file_count=index.file_count, symbol_count=len(index.symbols),
                         parse_coverage=index.parsed_count / max(1, index.python_count),
                         diagnostics=index.diagnostics)
    return {"index_ref": state["repository"]["tree_hash"]}
