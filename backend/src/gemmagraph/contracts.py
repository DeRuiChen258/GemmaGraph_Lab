from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Method = Literal["lexical", "lexical_graph", "lexical_graph_budget"]
RunStatus = Literal["queued", "running", "awaiting_review", "completed", "blocked", "failed", "cancelled"]


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_attempts: int = Field(3, ge=1, le=10)
    max_model_calls: int = Field(12, ge=2, le=50)
    active_timeout_seconds: int = Field(900, ge=10, le=7200)
    test_timeout_seconds: int = Field(120, ge=1, le=600)
    evidence_tokens: int = Field(8000, ge=128, le=65536)
    max_changed_files: int = Field(5, ge=1, le=20)


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository_id: str
    issue: str = Field(min_length=5, max_length=30000)
    method: Method = "lexical_graph_budget"
    test_profile_id: str = "python-pytest"
    budget: Budget = Field(default_factory=Budget)
    seed: int = Field(42, ge=0, le=2**31 - 1)
    parent_run_id: str | None = None


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: str
    patch_hash: str
    decision: Literal["accept", "reject", "revise"]
    feedback: str = Field(default="", max_length=6000)


class DatasetImport(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    repository_map: dict[str, str] = {}


class RepositoryRecord(BaseModel):
    id: str
    name: str
    snapshot_id: str
    tree_hash: str
    created_at: str
    index_status: str = "queued"
    file_count: int = 0
    symbol_count: int = 0
    parse_coverage: float | None = None
    diagnostics: list[dict[str, Any]] = []


class RunRecord(BaseModel):
    id: str
    repository_id: str
    repository_name: str
    issue: str
    status: RunStatus
    outcome: str = "pending"
    method: Method
    current_node: str | None = None
    attempt: int = 0
    created_at: str
    updated_at: str
    config_snapshot: dict[str, Any]
    usage: dict[str, Any] = {}
    evidence: list[dict[str, Any]] = []
    plan: dict[str, Any] | None = None
    baseline: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    patch: dict[str, Any] | None = None
    review: dict[str, Any] | None = None
    review_status: str = "not_requested"
    error: dict[str, Any] | None = None
    summary: str | None = None
    cancel_requested: bool = False
    experiment_id: str | None = None


class DatasetRecord(BaseModel):
    id: str
    name: str
    sha256: str
    task_count: int
    created_at: str
    tasks: list[dict[str, Any]]


class ExperimentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    dataset_id: str
    arms: list[Method] = Field(default=["lexical", "lexical_graph", "lexical_graph_budget"], min_length=1)
    seeds: list[int] = Field(default=[42], min_length=1, max_length=10)
    budget: Budget = Field(default_factory=Budget)


class ExperimentRecord(BaseModel):
    id: str
    name: str
    dataset_id: str
    status: str
    created_at: str
    config: dict[str, Any]
    run_ids: list[str] = []
    metrics: list[dict[str, Any]] = []
    export_id: str | None = None


class ArtifactRecord(BaseModel):
    id: str
    run_id: str
    name: str
    sha256: str
    size: int
    media_type: str
    created_at: str


class EventRecord(BaseModel):
    schema_version: int = 1
    run_id: str
    seq: int
    timestamp: str
    type: str
    node: str | None = None
    attempt: int = 0
    payload: dict[str, Any] = {}


class Page(BaseModel):
    items: list[Any]
    next_cursor: str | None = None
