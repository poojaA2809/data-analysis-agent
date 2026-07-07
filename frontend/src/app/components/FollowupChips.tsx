'use client'

/**
 * Clickable follow-up suggestion chips. Clicking a chip calls `onPick` with the
 * chip's question text; the page submits it through the same streaming ask path.
 * Renders nothing when there are no follow-ups.
 */
export function FollowupChips({
  followups,
  onPick,
  disabled,
}: {
  followups: string[]
  onPick: (question: string) => void
  disabled?: boolean
}) {
  const chips = Array.isArray(followups) ? followups.filter((f) => f && f.trim()) : []
  if (chips.length === 0) return null

  return (
    <div data-testid="followups">
      <div className="mb-2 text-xs font-medium text-gray-500">Suggested follow-ups</div>
      <div className="flex flex-wrap gap-2">
        {chips.map((c, i) => (
          <button
            key={`${i}-${c}`}
            type="button"
            data-testid="followup-chip"
            disabled={disabled}
            onClick={() => onPick(c)}
            className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700 transition hover:border-blue-300 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {c}
          </button>
        ))}
      </div>
    </div>
  )
}
