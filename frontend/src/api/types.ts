export type Method = 'lexical' | 'lexical_graph' | 'lexical_graph_budget'
export type RunStatus = 'queued' | 'running' | 'awaiting_review' | 'completed' | 'blocked' | 'failed' | 'cancelled'
export type ModelUsage = Record<string, number | string | null | undefined>

export interface Repository {
  id: string; name: string; snapshot_id: string; tree_hash: string; created_at: string
  index_status: string; file_count: number; symbol_count: number
  parse_coverage: number | null; diagnostics: Array<Record<string, unknown>>
}

export interface Run {
  id: string; repository_id: string; repository_name: string; issue: string; status: RunStatus
  outcome: string; method: Method; current_node: string | null; attempt: number; created_at: string
  updated_at: string; config_snapshot: { method: Method; budget: Budget; model: Record<string, unknown>; prompt_version?: string }
  usage: ModelUsage; evidence: Evidence[]; plan: Record<string, unknown> | null
  baseline: Verification | null; verification: Verification | null; patch: Artifact | null
  review: Review | null; review_status: string; error: { code: string; message: string } | null
  summary: string | null; cancel_requested: boolean
}

export interface Budget {
  max_attempts: number; max_model_calls: number; active_timeout_seconds: number
  test_timeout_seconds: number; evidence_tokens: number; max_changed_files: number
}

export interface Evidence {
  id: string; path: string; symbol_id: string; start_line: number; end_line: number
  score: number; relation_distance: number; relation_path: string; text: string
  tokens: number; token_count_mode: string; truncated: boolean
}

export interface Artifact {
  id: string; run_id: string; name: string; sha256: string; size: number; media_type: string
}

export interface Verification {
  exit_code: number | null; timed_out: boolean; collected: number; stdout: string; stderr: string
  environment_error: boolean; baseline_reproduced?: boolean; tests_passed?: boolean; outcome?: string
  artifact_id?: string
}

export interface Review {
  review_id: string; patch_hash: string | null; patch: Artifact | null
  verification: Verification | null; outcome: string; plan: Record<string, unknown> | null
  baseline: Verification | null; actions: string[]; status?: string; feedback?: string
}

export interface RunEvent {
  schema_version: number; run_id: string; seq: number; timestamp: string; type: string
  node?: string; attempt?: number; payload?: Record<string, unknown>
}

export interface Experiment {
  id: string; name: string; dataset_id: string; status: string; created_at: string
  config: Record<string, unknown>; run_ids?: string[]; metrics?: Metric[]; runs?: ExperimentItem[]
}

export interface ExperimentItem {
  run_id: string; instance_id: string; method: Method; seed: number; status: string; outcome: string
  verification: Verification | null; usage: ModelUsage
  error: Record<string, unknown> | null
}

export interface Metric {
  method: Method; planned: number; completed: number; solved: number; solve_rate: number
  environment_errors: number; input_tokens: number | null; output_tokens: number | null; thought_tokens?: number | null; activity_seconds: number | null
  items?: ExperimentItem[]
}

export interface TaskDataset {
  id: string; name: string; sha256: string; task_count: number; created_at: string
  tasks: Array<Record<string, unknown>>
}

export interface ModelStatus {
  configured: boolean; provider: string; model_id: string; base_url: string; key_configured: boolean
  model_path?: string; runtime_path?: string; model_file_exists?: boolean; runtime_exists?: boolean
  device?: string; cuda_toolkit_version?: string; transport?: string; context_window?: number; max_output_tokens?: number; revision?: string | null
}

export interface AppSettings {
  defaults: Budget & Record<string, number>; profiles: Array<{ id: string; command: string[]; memory_mb: number; timeout_seconds: number }>
  model: ModelStatus
  sandbox: { available: boolean; reason?: string; engine_version?: string }
}

export interface Overview {
  repositories: number; runs: number; by_status: Record<string, number>; experiments: number
  recent_runs: Run[]; model: ModelStatus
  sandbox: { available: boolean; reason?: string; engine_version?: string }
}

export interface GraphResponse {
  nodes: Array<{ id: string; path: string; name: string; kind: string; start_line: number; end_line: number }>
  edges: Array<{ source: string; target: string; kind: string; confidence: string }>
  truncated: boolean; total_nodes: number; coverage: number
}
