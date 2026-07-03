'use client'

import { ChartCard, TableCard } from './RichOutput'
import type { DashboardPayload } from '../lib/api'

// A capped number of data-grid rows to actually render in the browser. The
// backend already caps its sample (AGENT_GRID_ROW_CAP); this is a second,
// purely-visual guard so a large sample never floods the DOM.
const GRID_RENDER_CAP = 200

/**
 * Renders an auto-generated dashboard for one dataset: a title, a responsive
 * grid of charts (reusing the Phase-3 recharts renderer), a summary/aggregation
 * table, a written-insights list, and a capped/scrollable data grid of the
 * actual records. Every section is defensive — empty or missing arrays render a
 * graceful placeholder or nothing, and odd data never throws.
 *
 * The "Export / Share" control is a clearly-labelled, disabled Phase-B stub.
 */
export function Dashboard({ payload }: { payload: DashboardPayload }) {
  const charts = Array.isArray(payload.charts) ? payload.charts : []
  const insights = Array.isArray(payload.insights) ? payload.insights : []
  const summary = payload.summary_table ?? null
  const grid = payload.data_grid ?? null

  const gridColumns = Array.isArray(grid?.columns) ? grid!.columns! : []
  const gridRows = Array.isArray(grid?.rows) ? grid!.rows! : []
  const shownRows = gridRows.slice(0, GRID_RENDER_CAP)
  const totalRows =
    typeof grid?.total_rows === 'number' ? grid!.total_rows! : gridRows.length

  const hasAnything =
    charts.length > 0 || insights.length > 0 || summary != null || grid != null

  return (
    <section
      data-testid="dashboard"
      aria-label="Auto-generated dashboard"
      className="rounded-xl border border-gray-200 bg-white/70 p-5 shadow-sm"
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2
            data-testid="dashboard-title"
            className="text-lg font-bold tracking-tight text-gray-900"
          >
            {payload.title?.trim() || 'Dashboard'}
          </h2>
          <p className="mt-0.5 text-xs text-gray-500">
            Automatically generated from your dataset — no question needed.
          </p>
        </div>
        {/* Phase-B stub: export/share is built in the next phase. Clearly
            labelled and disabled so it is never mistaken for a bug. */}
        <button
          type="button"
          disabled
          data-testid="dashboard-export-stub"
          title="Coming in Phase B"
          className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg border border-gray-200 bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-400"
        >
          Export / Share
          <span className="rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
            Coming soon
          </span>
        </button>
      </div>

      {!hasAnything && (
        <div className="rounded-lg border border-dashed border-gray-300 p-6 text-center text-sm text-gray-500">
          The dashboard has no content to display for this dataset.
        </div>
      )}

      {/* Charts — responsive grid, reusing the shared recharts renderer. */}
      {charts.length > 0 && (
        <div
          data-testid="dashboard-charts"
          className="grid grid-cols-1 gap-4 lg:grid-cols-2"
        >
          {charts.map((c, i) => (
            <ChartCard key={i} spec={c} />
          ))}
        </div>
      )}

      {/* Insights — 2–5 written takeaways. */}
      {insights.length > 0 && (
        <div className="mt-5" data-testid="dashboard-insights">
          <h3 className="mb-2 text-sm font-semibold text-gray-800">Key insights</h3>
          <ul className="space-y-2">
            {insights.map((text, i) => (
              <li
                key={i}
                data-testid="dashboard-insight"
                className="flex items-start gap-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-sm text-gray-800"
              >
                <span aria-hidden="true" className="mt-0.5 text-blue-500">
                  •
                </span>
                <span>{String(text)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Summary / aggregation table — reuse the Phase-3 table styling. */}
      {summary && (
        <div className="mt-5" data-testid="dashboard-summary">
          <TableCard table={summary} />
        </div>
      )}

      {/* Data grid — a capped, scrollable sample of the actual records. */}
      {grid && (
        <div className="mt-5" data-testid="dashboard-grid">
          <h3 className="mb-2 text-sm font-semibold text-gray-800">Records</h3>
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <div className="max-h-96 overflow-auto">
              <table className="min-w-full text-sm">
                {gridColumns.length > 0 && (
                  <thead className="sticky top-0 bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
                    <tr>
                      {gridColumns.map((c, i) => (
                        <th key={i} className="px-4 py-2">
                          {String(c)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody className="divide-y divide-gray-100">
                  {shownRows.length === 0 ? (
                    <tr>
                      <td
                        className="px-4 py-3 text-gray-400"
                        colSpan={Math.max(gridColumns.length, 1)}
                      >
                        No records to display.
                      </td>
                    </tr>
                  ) : (
                    shownRows.map((row, ri) => {
                      const cells = Array.isArray(row) ? row : [row]
                      return (
                        <tr key={ri} className="hover:bg-gray-50">
                          {cells.map((cell, ci) => (
                            <td key={ci} className="px-4 py-2 text-gray-800">
                              {cell == null ? '' : String(cell)}
                            </td>
                          ))}
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>
          <p
            data-testid="dashboard-grid-caption"
            className="mt-1.5 text-xs text-gray-500"
          >
            Showing {shownRows.length} of {totalRows} rows
          </p>
        </div>
      )}
    </section>
  )
}
