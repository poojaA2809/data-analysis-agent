// A small, consistent "Coming soon" badge used to mark every non-functional
// Phase-1 stub so a greyed-out surface is never mistaken for a bug.

export function ComingSoonBadge({ phase = 'Coming soon' }: { phase?: string }) {
  return (
    <span
      className="inline-flex items-center rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
      aria-label={`${phase} — not yet available`}
    >
      {phase}
    </span>
  )
}
