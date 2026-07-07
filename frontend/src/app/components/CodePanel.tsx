'use client'

import { useState } from 'react'

/**
 * Collapsible "Code that ran" panel — collapsed by default. Shows the exact
 * Python the agent executed, verbatim, in a monospace block. This is a core
 * Phase-1 trust signal, so it is real (not a stub).
 */
export function CodePanel({ code }: { code: string }) {
  const [open, setOpen] = useState(false)
  const panelId = 'code-that-ran'

  return (
    <div className="mt-3 overflow-hidden rounded-lg border border-gray-200">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center justify-between bg-gray-50 px-4 py-2.5 text-left text-sm font-medium text-gray-700 hover:bg-gray-100"
      >
        <span>Code that ran</span>
        <svg
          className={`h-4 w-4 text-gray-500 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>
      {open && (
        <pre
          id={panelId}
          data-testid="code-block"
          className="max-h-96 overflow-auto bg-gray-900 p-4 text-xs leading-relaxed text-gray-100"
        >
          <code className="font-mono">{code}</code>
        </pre>
      )}
    </div>
  )
}
