from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


def open_checkpointer(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return AsyncSqliteSaver.from_conn_string(str(settings.data_dir / "checkpoints.sqlite3"))
