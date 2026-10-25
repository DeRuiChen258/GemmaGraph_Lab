import type { AppSettings, Artifact, Experiment, GraphResponse, Overview, Repository, Run, TaskDataset } from './types'

const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code: string, readonly requestId?: string) {
    super(message); this.name = 'ApiError'
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  const isForm = typeof FormData !== 'undefined' && init.body instanceof FormData
  if (init.body && !isForm && typeof init.body === 'string') headers.set('Content-Type', 'application/json')
  headers.set('X-Request-ID', crypto.randomUUID())
  let response: Response
  try { response = await fetch(`${base}${path}`, { ...init, headers, credentials: 'omit' }) }
  catch { throw new ApiError('无法连接本地后端，请确认 API 正在运行。', 0, 'connection_failed') }
  if (!response.ok) {
    let body: { message?: string; code?: string; request_id?: string } = {}
    try { body = await response.json() } catch { /* Keep the HTTP status as a useful fallback. */ }
    throw new ApiError(body.message || `请求失败 (${response.status})`, response.status,
      body.code || 'http_error', body.request_id)
  }
  const type = response.headers.get('content-type') || ''
  return (!type.includes('application/json') && !type.includes('+json') ? response.blob() : response.json()) as Promise<T>
}

export const api = {
  overview: () => request<Overview>('/overview'),
  health: () => request<{ status: string; worker: { alive: boolean; last_seen_seconds: number | null }; database: string }>('/health'),
  settings: () => request<AppSettings>('/settings'),
  workflow: () => request<{ version: number; nodes: Array<{ id: string; label: string }>; edges: Array<{ source: string; target: string }> }>('/workflow'),
  updateSettings: (defaults: Partial<AppSettings['defaults']>) =>
    request('/settings', { method: 'PATCH', body: JSON.stringify({ defaults }) }),
  checkProvider: () => request<Record<string, unknown>>('/providers/check', { method: 'POST', body: '{}' }),
  repositories: () => request<{ items: Repository[] }>('/repositories'),
  repository: (id: string) => request<Repository>(`/repositories/${encodeURIComponent(id)}`),
  importRepository: (name: string, file: File) => {
    const data = new FormData(); data.set('name', name); data.set('archive', file)
    return request<Repository>('/repositories', { method: 'POST', body: data })
  },
  tree: (id: string, directory = '') => request<{ items: Array<{ name: string; path: string; type: 'file' | 'directory'; size: number | null }> }>(
    `/repositories/${encodeURIComponent(id)}/tree?directory=${encodeURIComponent(directory)}`),
  file: (id: string, path: string, start = 1) => request<{ path: string; start_line: number; end_line: number; content: string; total_lines: number }>(
    `/repositories/${encodeURIComponent(id)}/file?path=${encodeURIComponent(path)}&start_line=${start}`),
  graph: (id: string, query = '', node?: string) => request<GraphResponse>(
    `/repositories/${encodeURIComponent(id)}/graph?hops=1&limit=180${query ? `&query=${encodeURIComponent(query)}` : ''}${node ? `&node=${encodeURIComponent(node)}` : ''}`),
  runs: (status?: string) => request<{ items: Run[] }>(`/runs${status ? `?status=${encodeURIComponent(status)}` : ''}`),
  run: (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}`),
  runHistory: (id: string, after = 0) => request<{ items: import('./types').RunEvent[]; next_seq: number }>(
    `/runs/${encodeURIComponent(id)}/events/history?after_seq=${after}`),
  createRun: (input: { repository_id: string; issue: string; method: Run['method'];
    test_profile_id: string; budget?: Partial<Run['config_snapshot']['budget']> }) =>
    request<Run>('/runs', { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify(input) }),
  cancelRun: (id: string) => request<Run>(`/runs/${encodeURIComponent(id)}/cancel`, { method: 'POST', body: '{}' }),
  resumeRun: (id: string, body: { review_id: string; patch_hash: string; decision: 'accept' | 'reject' | 'revise'; feedback: string }) =>
    request<Run>(`/runs/${encodeURIComponent(id)}/resume`, { method: 'POST',
      headers: { 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify(body) }),
  artifacts: (id: string) => request<{ items: Artifact[] }>(`/runs/${encodeURIComponent(id)}/artifacts`),
  artifact: (id: string) => request<Blob>(`/artifacts/${encodeURIComponent(id)}`),
  datasets: () => request<{ items: Array<Omit<TaskDataset, 'tasks'>> }>('/datasets'),
  importDataset: (file: File, repositoryMap: Record<string, string>) => {
    const data = new FormData(); data.set('file', file); data.set('name', file.name)
    data.set('repository_map', JSON.stringify(repositoryMap))
    return request<TaskDataset>('/datasets/import', { method: 'POST', body: data })
  },
  experiments: () => request<{ items: Experiment[] }>('/experiments'),
  experiment: (id: string) => request<Experiment>(`/experiments/${encodeURIComponent(id)}`),
  createExperiment: (input: { name: string; dataset_id: string; arms: Run['method'][]; seeds: number[] }) =>
    request<Experiment>('/experiments', { method: 'POST', headers: { 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify(input) }),
  cancelExperiment: (id: string) => request(`/experiments/${encodeURIComponent(id)}/cancel`, { method: 'POST', body: '{}' }),
  exportExperiment: (id: string) => request<Blob>(`/experiments/${encodeURIComponent(id)}/export`, { method: 'POST', body: '{}' }),
}

export function artifactUrl(id: string) { return `${base}/artifacts/${encodeURIComponent(id)}` }
export function runEventsUrl(id: string, after: number) {
  return `${base}/runs/${encodeURIComponent(id)}/events?after_seq=${after}`
}
