'use client'

/**
 * Live step indicator driven by SSE `step` events. Shows a spinner plus the
 * current step label while a run is active; renders nothing when idle (no
 * active label).
 */
export function StepIndicator({ label }: { label: string | null }) {
  if (!label) return null
  return (
    <div
      data-testid="step-indicator"
      className="mb-4 flex items-center gap-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-blue-700"
      role="status"
      aria-live="polite"
    >
      <svg className="h-4 w-4 animate-spin text-blue-600" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8V0C5.4 0 0 5.4 0 12h4z" />
      </svg>
      <span data-testid="step-label">{label}</span>
    </div>
  )
}
