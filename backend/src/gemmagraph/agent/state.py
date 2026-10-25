from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    schema_version: int
    run_id: str
    thread_id: str
    task_id: str
    repository_id: str
    repository: dict[str, Any]
    issue: str
    config_snapshot: dict[str, Any]
    review_policy: str
    source_snapshot: str
    workspace_ref: str
    index_ref: str
    evidence: list[dict[str, Any]]
    plan: dict[str, Any] | None
    patch_ref: dict[str, Any] | None
    patch_hash: str | None
    patch_text: str | None
    patch_validation: dict[str, Any]
    attempt: int
    baseline_result_ref: dict[str, Any] | None
    verification_ref: dict[str, Any] | None
    usage: dict[str, Any]
    reflection: dict[str, Any] | None
    review: dict[str, Any] | None
    outcome: str
    error: dict[str, Any] | None
    summary: str | None
