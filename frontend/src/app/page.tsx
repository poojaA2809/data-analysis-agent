'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Dropzone, type UploadedFile } from './components/Dropzone'
import { CodePanel } from './components/CodePanel'
import { ProfileCard } from './components/ProfileCard'
import { HistorySidebar } from './components/HistorySidebar'
import { DatasetPicker } from './components/DatasetPicker'
import { RichOutput } from './components/RichOutput'
import { Dashboard } from './components/Dashboard'
import { CostBar } from './components/CostBar'
import { FollowupChips } from './components/FollowupChips'
import { StepIndicator } from './components/StepIndicator'
import {
  askQuestion,
  askQuestionStream,
  createSession,
  generateDashboard,
  getSession,
  listSessions,
  uploadDataset,
  type DashboardPayload,
  type MessageData,
  type SessionSummary,
  type StreamEvent,
} from './lib/api'

type Turn = {
  id: string
  question: string
  answer: string | null
  code: string | null
  status: string
  error: string | null
  clarify: string | null
  data: MessageData | null
}

type QueryCost = {
  prompt_tokens: number | null
  completion_tokens: number | null
  cost_usd: number | null
}

const LAST_SESSION_KEY = 'daa.lastSessionId'

export default function Home() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [files, setFiles] = useState<UploadedFile[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [question, setQuestion] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState<string | null>(null)
  const [stepLabel, setStepLabel] = useState<string | null>(null)
  const [queryCost, setQueryCost] = useState<QueryCost | null>(null)
  const [usageKey, setUsageKey] = useState(0)

  // Auto-dashboard (Phase A): built automatically after a CSV upload, no
  // question required. `dashboard` holds the rendered payload, `dashboardLoading`
  // drives the "Building your dashboard…" state, `dashboardError` surfaces a
  // failure without breaking the rest of the page.
  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null)
  const [dashboardLoading, setDashboardLoading] = useState(false)
  const [dashboardError, setDashboardError] = useState<string | null>(null)

  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Keep the freshest session id in a ref so an upload + ask in quick
  // succession don't race on stale state.
  const sessionRef = useRef<string | null>(null)
  function setSession(id: string) {
    sessionRef.current = id
    setSessionId(id)
    try {
      localStorage.setItem(LAST_SESSION_KEY, id)
    } catch {
      /* localStorage may be unavailable; non-fatal */
    }
  }

  const refreshHistory = useCallback(async () => {
    try {
      const list = await listSessions()
      setSessions(list)
    } catch {
      setSessions([])
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const openSession = useCallback(async (id: string) => {
    try {
      const detail = await getSession(id)
      setSession(detail.session.id)
      // Restore the loaded datasets (with their profile cards).
      setFiles(
        detail.datasets.map((d) => ({
          datasetId: d.id,
          filename: d.filename,
          sizeBytes: d.size_bytes,
          fileType: d.file_type,
          profile: d.profile ?? null,
        })),
      )
      setSelected(new Set(detail.datasets.map((d) => d.id)))
      // Rebuild the conversation thread from run history: each run -> a Q&A turn
      // carrying its answer + generated code. Prior runs have no persisted
      // charts/cost, so restored turns render answer + code only (rich output
      // and per-query cost are omitted for them).
      const restoredTurns: Turn[] = (detail.runs ?? []).map((r) => {
        const failed = r.status === 'failed' || !r.answer_text
        return {
          id: r.id,
          question: r.question,
          answer: r.answer_text,
          code: r.generated_code,
          status: r.status ?? (r.answer_text ? 'completed' : 'failed'),
          error: failed ? 'The analysis failed. Try asking again.' : null,
          clarify: null,
          data: null,
        }
      })
      setTurns(restoredTurns)
      setAskError(null)
      setQueryCost(null)
    } catch (err) {
      // Surface the failure instead of hiding it — a silent reset here is what
      // made a reload look like "No questions yet…" when restore actually broke.
      console.error(`Failed to restore session ${id}:`, err)
      const status = (err as { status?: number } | null)?.status
      if (status === 404) {
        try {
          localStorage.removeItem(LAST_SESSION_KEY)
        } catch {
          /* non-fatal */
        }
      }
    }
  }, [])

  // On mount: load the sidebar and restore the last session (if any).
  useEffect(() => {
    void refreshHistory()
    let last: string | null = null
    try {
      last = localStorage.getItem(LAST_SESSION_KEY)
    } catch {
      last = null
    }
    if (last) void openSession(last)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function newSession() {
    sessionRef.current = null
    setSessionId(null)
    setFiles([])
    setSelected(new Set())
    setTurns([])
    setAskError(null)
    setQuestion('')
    setStepLabel(null)
    setQueryCost(null)
    setDashboard(null)
    setDashboardLoading(false)
    setDashboardError(null)
    try {
      localStorage.removeItem(LAST_SESSION_KEY)
    } catch {
      /* non-fatal */
    }
  }

  function toggleSelected(datasetId: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(datasetId)) next.delete(datasetId)
      else next.add(datasetId)
      return next
    })
  }

  async function handleFile(file: File) {
    const ds = await uploadDataset(file, sessionRef.current)
    // The server creates a session on first upload if none was supplied.
    if (!sessionRef.current) setSession(ds.session_id)
    setFiles((prev) => [
      ...prev,
      {
        datasetId: ds.dataset_id,
        filename: ds.filename,
        sizeBytes: ds.size_bytes,
        fileType: ds.file_type,
        profile: ds.profile ?? null,
      },
    ])
    setSelected((prev) => new Set(prev).add(ds.dataset_id))
    void refreshHistory()

    // Auto-trigger the dashboard for the just-uploaded dataset — no user
    // question required. Failures are surfaced inline and never break the page
    // or block the ask UI.
    setDashboard(null)
    setDashboardError(null)
    setDashboardLoading(true)
    try {
      const payload = await generateDashboard(ds.dataset_id, sessionRef.current)
      if (payload.status === 'failed') {
        setDashboardError(
          payload.error?.trim() ||
            'The dashboard could not be generated for this file. You can still ask questions below.',
        )
        setDashboard(null)
      } else {
        setDashboard(payload)
      }
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : 'The dashboard could not be generated for this file.'
      setDashboardError(msg)
    } finally {
      setDashboardLoading(false)
    }
  }

  // Apply a finalized MessageData payload to the active turn (both the streamed
  // and the synchronous-fallback path funnel through here).
  const finalizeTurn = useCallback((turnId: string, res: MessageData) => {
    const clarify = res.needs_clarification ?? null
    const failed = res.status === 'failed' || (!res.answer_text && !clarify)
    setTurns((prev) =>
      prev.map((t) =>
        t.id === turnId
          ? {
              ...t,
              status: res.status,
              answer: clarify ? null : res.answer_text,
              code: clarify ? null : res.generated_code,
              clarify,
              data: clarify ? null : res,
              error: failed
                ? 'The analysis failed. Try rephrasing your question or re-uploading the file.'
                : null,
            }
          : t,
      ),
    )
    setQueryCost({
      prompt_tokens: res.prompt_tokens,
      completion_tokens: res.completion_tokens,
      cost_usd: res.cost_usd,
    })
  }, [])

  const runQuestion = useCallback(
    async (rawQuestion: string) => {
      const q = rawQuestion.trim()
      if (!q || asking) return
      if (files.length === 0) {
        setAskError('Upload a CSV or Excel file first, then ask a question about it.')
        return
      }
      const datasetIds = files.filter((f) => selected.has(f.datasetId)).map((f) => f.datasetId)
      if (datasetIds.length === 0) {
        setAskError('Select at least one dataset to include in your question.')
        return
      }
      setAskError(null)
      setAsking(true)
      setStepLabel('Starting…')

      const turnId = crypto.randomUUID()
      setTurns((prev) => [
        ...prev,
        {
          id: turnId,
          question: q,
          answer: null,
          code: null,
          status: 'running',
          error: null,
          clarify: null,
          data: null,
        },
      ])
      setQuestion('')
      queueMicrotask(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }))

      try {
        let sid = sessionRef.current
        if (!sid) {
          const s = await createSession()
          sid = s.session_id
          setSession(sid)
        }

        let streamedText = ''
        let sawClarify = false

        const onEvent = (ev: StreamEvent) => {
          if (ev.kind === 'step') {
            setStepLabel(ev.label)
          } else if (ev.kind === 'token') {
            streamedText += ev.text
            const text = streamedText
            setTurns((prev) =>
              prev.map((t) => (t.id === turnId ? { ...t, answer: text } : t)),
            )
          } else if (ev.kind === 'clarify') {
            sawClarify = true
            const cq = ev.question
            setTurns((prev) =>
              prev.map((t) =>
                t.id === turnId ? { ...t, clarify: cq, answer: null, code: null } : t,
              ),
            )
          } else if (ev.kind === 'done') {
            finalizeTurn(turnId, ev.data)
          }
        }

        let result: MessageData | null
        try {
          result = await askQuestionStream(sid, q, datasetIds, onEvent)
          // If the stream ended without a terminal `done` (and it wasn't a
          // clarify turn), treat it as a failure and fall back.
          if (!result && !sawClarify) {
            throw new Error('Stream ended without a final result.')
          }
        } catch (streamErr) {
          console.warn('Streaming ask failed; falling back to synchronous ask.', streamErr)
          setStepLabel('Analyzing…')
          const res = await askQuestion(sid, q, datasetIds)
          finalizeTurn(turnId, res)
        }

        void refreshHistory()
        setUsageKey((k) => k + 1)
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : 'Something went wrong running the analysis.'
        setTurns((prev) =>
          prev.map((t) => (t.id === turnId ? { ...t, status: 'failed', error: msg } : t)),
        )
      } finally {
        setAsking(false)
        setStepLabel(null)
        queueMicrotask(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }))
      }
    },
    [asking, files, selected, refreshHistory, finalizeTurn],
  )

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault()
    await runQuestion(question)
  }

  const handleFollowup = useCallback(
    (q: string) => {
      void runQuestion(q)
    },
    [runQuestion],
  )

  const profiledFiles = files.filter((f) => f.profile)

  return (
    <div className="flex min-h-screen flex-col">
      <div className="flex flex-1 overflow-hidden">
        <HistorySidebar
          sessions={sessions}
          activeId={sessionId}
          loading={historyLoading}
          onSelect={(id) => void openSession(id)}
          onNew={newSession}
        />

        <main className="flex flex-1 flex-col overflow-y-auto">
          <div className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">
            <header className="mb-6">
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">
                Data Analysis Agent
              </h1>
              <p className="mt-1 text-sm text-gray-500">
                Upload CSV or Excel files, ask a question in plain language, and see the
                exact Python the agent ran. Your data stays on your machine.
              </p>
            </header>

            <section className="mb-4" aria-label="Upload data">
              <Dropzone onFile={handleFile} files={files} disabled={asking} />
            </section>

            {files.length > 0 && (
              <section className="mb-4">
                <DatasetPicker
                  files={files}
                  selected={selected}
                  onToggle={toggleSelected}
                />
              </section>
            )}

            {profiledFiles.length > 0 && (
              <section
                className="mb-6 space-y-3"
                aria-label="Dataset profiles"
                data-testid="profiles"
              >
                {profiledFiles.map((f) => (
                  <ProfileCard
                    key={f.datasetId}
                    filename={f.filename}
                    fileType={f.fileType}
                    profile={f.profile!}
                  />
                ))}
              </section>
            )}

            {(dashboardLoading || dashboardError || dashboard) && (
              <section className="mb-6" aria-label="Dashboard" data-testid="dashboard-section">
                {dashboardLoading && (
                  <div
                    data-testid="dashboard-loading"
                    className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white p-5 text-sm text-gray-600 shadow-sm"
                  >
                    <svg
                      className="h-5 w-5 animate-spin text-blue-600"
                      viewBox="0 0 24 24"
                      fill="none"
                      aria-hidden="true"
                    >
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.4 0 0 5.4 0 12h4z" />
                    </svg>
                    Building your dashboard… this runs a few analyses and may take a moment.
                  </div>
                )}

                {!dashboardLoading && dashboardError && (
                  <div
                    role="alert"
                    data-testid="dashboard-error"
                    className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
                  >
                    Couldn&apos;t build the dashboard: {dashboardError}
                  </div>
                )}

                {!dashboardLoading && !dashboardError && dashboard && (
                  <Dashboard payload={dashboard} />
                )}
              </section>
            )}

            <form onSubmit={handleAsk} className="mb-6" aria-label="Ask a question">
              <label htmlFor="question" className="mb-1 block text-sm font-medium text-gray-700">
                Ask a question about your data
              </label>
              <div className="flex gap-2">
                <input
                  id="question"
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  disabled={asking}
                  placeholder="e.g. What is the average order value by region?"
                  className="flex-1 rounded-lg border border-gray-300 px-3 py-2.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50"
                />
                <button
                  type="submit"
                  disabled={asking || !question.trim()}
                  className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {asking && (
                    <svg
                      className="h-4 w-4 animate-spin"
                      viewBox="0 0 24 24"
                      fill="none"
                      aria-hidden="true"
                    >
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.4 0 0 5.4 0 12h4z" />
                    </svg>
                  )}
                  {asking ? 'Analyzing…' : 'Ask'}
                </button>
              </div>
              {askError && (
                <p role="alert" className="mt-2 text-sm text-red-600">
                  {askError}
                </p>
              )}
            </form>

            <StepIndicator label={stepLabel} />

            <section className="mt-6 space-y-6" aria-label="Conversation" data-testid="conversation">
              {turns.length === 0 && (
                <div className="rounded-lg border border-dashed border-gray-300 bg-white/60 p-8 text-center">
                  <p className="text-sm text-gray-500">
                    No questions yet. Upload a file above and ask your first question — your
                    answer and the exact code will appear here.
                  </p>
                </div>
              )}

              {turns.map((turn) => (
                <article key={turn.id} className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                  <p className="mb-3 text-sm font-semibold text-gray-900">{turn.question}</p>

                  {turn.status === 'running' && !turn.answer && !turn.error && !turn.clarify && (
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <svg className="h-4 w-4 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.4 0 0 5.4 0 12h4z" />
                      </svg>
                      Analyzing…
                    </div>
                  )}

                  {turn.clarify && (
                    <div
                      data-testid="clarify-prompt"
                      role="status"
                      className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
                    >
                      <p className="mb-1 font-semibold">I need a bit more detail</p>
                      <p className="leading-relaxed">{turn.clarify}</p>
                    </div>
                  )}

                  {turn.error && (
                    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                      The analysis failed: {turn.error}
                    </div>
                  )}

                  {turn.answer && (
                    <div
                      data-testid="answer-pane"
                      className="whitespace-pre-wrap text-sm leading-relaxed text-gray-800"
                    >
                      {turn.answer}
                    </div>
                  )}

                  {turn.code && <CodePanel code={turn.code} />}

                  {turn.data && <RichOutput data={turn.data} />}

                  {turn.data && turn.data.followups && turn.data.followups.length > 0 && (
                    <div className="mt-4">
                      <FollowupChips
                        followups={turn.data.followups}
                        onPick={handleFollowup}
                        disabled={asking}
                      />
                    </div>
                  )}
                </article>
              ))}
              <div ref={bottomRef} />
            </section>
          </div>
        </main>
      </div>

      <CostBar query={queryCost} refreshKey={usageKey} />
    </div>
  )
}
