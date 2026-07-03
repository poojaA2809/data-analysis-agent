// Single-origin API client. The static export is served by FastAPI at
// http://localhost:8001/app/, so every request uses a RELATIVE path and hits
// the same origin — no CORS, no configured base URL.
//
// All successful responses use the skeleton envelope `{ data, error }`.
// On an HTTP error the body is `{ detail: { code, message } }`. Both shapes
// are handled by `unwrap` below.

// A dataset profile is computed server-side (Phase 2) by `analysis/profiler.py`.
// These types mirror that REAL shape exactly; consumers still render
// defensively (any absent field is simply skipped) but target this shape.
export type NumericSummary = {
  mean?: number | null
  std?: number | null
  min?: number | null
  max?: number | null
}

export type ProfileColumn = {
  name?: string
  dtype?: string
  non_null_count?: number | null
  null_count?: number | null
  null_pct?: number | null
  unique_count?: number | null
  is_numeric?: boolean
  summary?: NumericSummary | null
  outlier_count?: number | null
  top_values?: { value: unknown; count: number }[] | null
  [key: string]: unknown
}

export type ProfileQuality = {
  missing_value_columns?: { name?: string; null_count?: number; null_pct?: number }[] | null
  duplicate_row_count?: number | null
  outlier_columns?: { name?: string; outlier_count?: number }[] | null
}

export type Profile = {
  filename?: string | null
  summary?: string | null
  row_count?: number | null
  column_count?: number | null
  columns?: ProfileColumn[] | null
  quality?: ProfileQuality | null
  [key: string]: unknown
}

export type DatasetData = {
  dataset_id: string
  session_id: string
  filename: string
  file_type: string
  size_bytes: number
  profile: Profile | null
}

export type SessionData = {
  session_id: string
  title: string | null
}

export type SessionSummary = {
  id: string
  title: string | null
  updated_at?: string | null
  created_at?: string | null
  dataset_count?: number | null
  message_count?: number | null
}

export type SessionDataset = {
  id: string
  filename: string
  file_type: string
  size_bytes: number
  profile: Profile | null
  created_at?: string | null
}

export type SessionMessage = {
  id?: string
  role: string
  content: string
  created_at?: string | null
}

export type SessionRun = {
  id: string
  question: string
  status?: string
  answer_text: string | null
  generated_code: string | null
  step_count: number | null
  created_at?: string | null
  completed_at?: string | null
}

export type SessionDetail = {
  session: SessionSummary
  datasets: SessionDataset[]
  messages: SessionMessage[]
  runs: SessionRun[]
}

export type MessageData = {
  run_id: string
  status: string
  answer_text: string | null
  generated_code: string | null
  step_count: number | null
  needs_clarification: string | null
  charts: unknown[]
  tables: unknown[]
  key_stats: unknown[]
  followups: unknown[]
  prompt_tokens: number | null
  completion_tokens: number | null
  cost_usd: number | null
}

/** Thrown for any non-2xx response or an envelope carrying an `error`. */
export class ApiError extends Error {
  code?: string
  status?: number
  constructor(message: string, opts: { code?: string; status?: number } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = opts.code
    this.status = opts.status
  }
}

type Envelope<T> = { data: T | null; error: unknown }
type ErrorBody = { detail?: { code?: string; message?: string } }

async function unwrap<T>(res: Response): Promise<T> {
  let body: unknown
  try {
    body = await res.json()
  } catch {
    throw new ApiError(`Server returned a non-JSON response (${res.status}).`, {
      status: res.status,
    })
  }

  if (!res.ok) {
    const detail = (body as ErrorBody)?.detail
    throw new ApiError(detail?.message ?? `Request failed (${res.status}).`, {
      code: detail?.code,
      status: res.status,
    })
  }

  const env = body as Envelope<T>
  if (env?.error) {
    const err = env.error as { message?: string; code?: string }
    throw new ApiError(err?.message ?? 'The request could not be completed.', {
      code: err?.code,
    })
  }
  if (env?.data == null) {
    throw new ApiError('The server returned an empty response.', {
      status: res.status,
    })
  }
  return env.data
}

/** Upload a CSV file. Creates a session server-side if `sessionId` is absent. */
export async function uploadDataset(
  file: File,
  sessionId?: string | null,
): Promise<DatasetData> {
  const form = new FormData()
  form.append('file', file)
  if (sessionId) form.append('session_id', sessionId)
  const res = await fetch('/datasets', { method: 'POST', body: form })
  return unwrap<DatasetData>(res)
}

/** Create a new session. */
export async function createSession(title?: string): Promise<SessionData> {
  const res = await fetch('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(title ? { title } : {}),
  })
  return unwrap<SessionData>(res)
}

/** List past sessions for the history sidebar (Phase 2). */
export async function listSessions(): Promise<SessionSummary[]> {
  const res = await fetch('/sessions', { method: 'GET' })
  const data = await unwrap<{ sessions: SessionSummary[] }>(res)
  return data.sessions ?? []
}

/** Load a full session (datasets, messages, run history) to reopen it. */
export async function getSession(sessionId: string): Promise<SessionDetail> {
  const res = await fetch(`/sessions/${sessionId}`, { method: 'GET' })
  return unwrap<SessionDetail>(res)
}

/** Ask a question against the given datasets in a session. */
export async function askQuestion(
  sessionId: string,
  question: string,
  datasetIds: string[],
): Promise<MessageData> {
  const res = await fetch(`/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, dataset_ids: datasetIds }),
  })
  return unwrap<MessageData>(res)
}
