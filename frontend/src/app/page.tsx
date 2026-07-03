'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Dropzone, type UploadedFile } from './components/Dropzone'
import { CodePanel } from './components/CodePanel'
import { ProfileCard } from './components/ProfileCard'
import { HistorySidebar } from './components/HistorySidebar'
import { DatasetPicker } from './components/DatasetPicker'
import {
  ChartsPlaceholder,
  CostBarStub,
  FollowupChipsStub,
  StepStreamStub,
} from './components/stubs'
import {
  askQuestion,
  createSession,
  getSession,
  listSessions,
  uploadDataset,
  type MessageData,
  type SessionSummary,
} from './lib/api'

type Turn = {
  id: string
  question: string
  answer: string | null
  code: string | null
  status: string
  error: string | null
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
      // carrying its answer + generated code, so the workspace shows prior turns
      // (incl. the answer pane) after a reload.
      const restoredTurns: Turn[] = (detail.runs ?? []).map((r) => {
        const failed = r.status === 'failed' || !r.answer_text
        return {
          id: r.id,
          question: r.question,
          answer: r.answer_text,
          code: r.generated_code,
          status: r.status ?? (r.answer_text ? 'completed' : 'failed'),
          error: failed ? 'The analysis failed. Try asking again.' : null,
        }
      })
      setTurns(restoredTurns)
      setAskError(null)
    } catch (err) {
      // Surface the failure instead of hiding it — a silent reset here is what
      // made a reload look like "No questions yet…" when restore actually broke.
      console.error(`Failed to restore session ${id}:`, err)
      // If a stored session no longer exists, drop the stale pointer so the next
      // load starts fresh rather than repeatedly failing.
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
  }

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault()
    const q = question.trim()
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

    const turnId = crypto.randomUUID()
    setTurns((prev) => [
      ...prev,
      { id: turnId, question: q, answer: null, code: null, status: 'running', error: null },
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
      const res: MessageData = await askQuestion(sid, q, datasetIds)
      const failed = res.status === 'failed' || !res.answer_text
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId
            ? {
                ...t,
                status: res.status,
                answer: res.answer_text,
                code: res.generated_code,
                error: failed
                  ? 'The analysis failed. Try rephrasing your question or re-uploading the file.'
                  : null,
              }
            : t,
        ),
      )
      void refreshHistory()
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : 'Something went wrong running the analysis.'
      setTurns((prev) =>
        prev.map((t) =>
          t.id === turnId ? { ...t, status: 'failed', error: msg } : t,
        ),
      )
    } finally {
      setAsking(false)
      queueMicrotask(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }))
    }
  }

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

            <StepStreamStub />

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

                  {turn.status === 'running' && !turn.answer && !turn.error && (
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <svg className="h-4 w-4 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.4 0 0 5.4 0 12h4z" />
                      </svg>
                      Analyzing…
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

                  {turn.answer && (
                    <div className="mt-4 space-y-4">
                      <ChartsPlaceholder />
                      <FollowupChipsStub />
                    </div>
                  )}
                </article>
              ))}
              <div ref={bottomRef} />
            </section>
          </div>
        </main>
      </div>

      <CostBarStub />
    </div>
  )
}
