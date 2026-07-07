'use client'

import type { SessionSummary } from '../lib/api'

function relTime(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const diff = Date.now() - d.getTime()
  const mins = Math.round(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.round(hrs / 24)
  if (days < 7) return `${days}d ago`
  return d.toLocaleDateString()
}

export function HistorySidebar({
  sessions,
  activeId,
  loading,
  onSelect,
  onNew,
}: {
  sessions: SessionSummary[]
  activeId: string | null
  loading: boolean
  onSelect: (id: string) => void
  onNew: () => void
}) {
  return (
    <aside
      data-testid="history-sidebar"
      className="hidden w-64 shrink-0 flex-col border-r border-gray-200 bg-gray-50/60 p-4 lg:flex"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-700">History</h2>
        <button
          type="button"
          onClick={onNew}
          data-testid="new-session"
          className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100"
        >
          + New
        </button>
      </div>

      {loading && (
        <div className="space-y-2" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-10 animate-pulse rounded-md bg-gray-200/70" />
          ))}
        </div>
      )}

      {!loading && sessions.length === 0 && (
        <p className="text-xs leading-relaxed text-gray-400">
          No past sessions yet. Upload a file and ask a question to start one — it
          will appear here so you can return to it later.
        </p>
      )}

      {!loading && sessions.length > 0 && (
        <ul className="space-y-1.5 overflow-y-auto" data-testid="session-list">
          {sessions.map((s) => {
            const active = s.id === activeId
            return (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => onSelect(s.id)}
                  className={[
                    'w-full rounded-md border px-3 py-2 text-left transition',
                    active
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-gray-200 bg-white hover:bg-gray-100',
                  ].join(' ')}
                >
                  <span className="block truncate text-xs font-medium text-gray-800">
                    {s.title?.trim() || 'Untitled session'}
                  </span>
                  <span className="mt-0.5 flex items-center gap-2 text-[11px] text-gray-400">
                    {relTime(s.updated_at ?? s.created_at) && (
                      <span>{relTime(s.updated_at ?? s.created_at)}</span>
                    )}
                    {typeof s.dataset_count === 'number' && (
                      <span>· {s.dataset_count} file{s.dataset_count === 1 ? '' : 's'}</span>
                    )}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </aside>
  )
}
