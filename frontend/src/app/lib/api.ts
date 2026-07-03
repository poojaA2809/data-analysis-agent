// Single-origin API client. The static export is served by FastAPI at
// http://localhost:8001/app/, so every request uses a RELATIVE path and hits
// the same origin — no CORS, no configured base URL.
//
// All successful responses use the skeleton envelope `{ data, error }`.
// On an HTTP error the body is `{ detail: { code, message } }`. Both shapes
// are handled by `unwrap` below.

export type DatasetData = {
  dataset_id: string
  session_id: string
  filename: string
  file_type: string
  size_bytes: number
  profile: unknown | null
}

export type SessionData = {
  session_id: string
  title: string | null
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
