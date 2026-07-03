// Clearly-labelled NON-FUNCTIONAL Phase-1 stubs.
//
// Each surface below is intentionally greyed and disabled and carries an
// explicit "Coming soon" badge so the user sees the product vision without
// ever mistaking a placeholder for a broken feature. These get wired for real
// in Phase 2 (history sidebar, profile card, multi-file) and Phase 3 (charts,
// cost bar, live step stream, follow-up chips).

import { ComingSoonBadge } from './ComingSoon'

// NOTE: The Phase-1 HistorySidebar and ProfileCardStub have been promoted to
// real Phase-2 components (`HistorySidebar.tsx`, `ProfileCard.tsx`). The stubs
// below remain clearly-labelled Phase-3 placeholders.

/** Charts + summary tables + key stats under the answer. Real in Phase 3. */
export function ChartsPlaceholder() {
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50/60 p-6 text-center opacity-70">
      <div className="mb-2 flex items-center justify-center gap-2">
        <span className="text-sm font-semibold text-gray-500">
          Charts, tables &amp; key stats
        </span>
        <ComingSoonBadge phase="Phase 3" />
      </div>
      <p className="text-xs leading-relaxed text-gray-400">
        Interactive charts, summary tables, and highlighted key statistics will
        render here beneath each answer.
      </p>
    </div>
  )
}

/** Follow-up suggestion chips. Real in Phase 3. */
export function FollowupChipsStub() {
  const chips = ['Break this down by month', 'Show the top 5', 'Compare to last year']
  return (
    <div className="opacity-60">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs font-medium text-gray-500">Suggested follow-ups</span>
        <ComingSoonBadge phase="Phase 3" />
      </div>
      <div className="flex flex-wrap gap-2">
        {chips.map((c) => (
          <button
            key={c}
            type="button"
            disabled
            className="cursor-not-allowed rounded-full border border-gray-300 bg-white px-3 py-1 text-xs text-gray-400"
          >
            {c}
          </button>
        ))}
      </div>
    </div>
  )
}

/** Live step stream ("Planning… / Running code… / Charting…"). Real in Phase 3. */
export function StepStreamStub() {
  const steps = ['Planning…', 'Running code…', 'Charting…']
  return (
    <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50/60 p-3 opacity-70">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-xs font-medium text-gray-500">Live progress</span>
        <ComingSoonBadge phase="Phase 3" />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {steps.map((s) => (
          <span
            key={s}
            className="rounded border border-gray-200 bg-white px-2 py-0.5 text-[11px] text-gray-400"
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  )
}

/** Bottom bar: this query's tokens + cost and today's running total. Real in Phase 3. */
export function CostBarStub() {
  return (
    <footer
      aria-hidden="true"
      className="flex select-none items-center justify-between border-t border-gray-200 bg-gray-50/80 px-4 py-2 text-xs text-gray-400"
    >
      <div className="flex items-center gap-2">
        <span className="font-medium text-gray-500">Cost &amp; tokens</span>
        <ComingSoonBadge phase="Phase 3" />
      </div>
      <div className="flex items-center gap-4">
        <span>This query: — tokens · $—</span>
        <span>Today: — tokens · $—</span>
      </div>
    </footer>
  )
}
