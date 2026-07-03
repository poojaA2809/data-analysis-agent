'use client'

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts'
import type { ChartPoint, ChartSpec, KeyStat, MessageData, TableSpec } from '../lib/api'

// A small palette used to distinguish grouped `series` within one chart.
const SERIES_COLORS = [
  '#2563eb',
  '#16a34a',
  '#d97706',
  '#dc2626',
  '#7c3aed',
  '#0891b2',
  '#db2777',
  '#65a30d',
]

function isNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

// Group a flat ChartPoint[] into series. When points carry a `series` field we
// pivot into wide rows keyed by x, with one numeric column per series so
// recharts can render grouped bars/lines. Otherwise we return a single "y" key.
function buildSeries(data: ChartPoint[]): {
  rows: Record<string, unknown>[]
  seriesKeys: string[]
  grouped: boolean
} {
  const hasSeries = data.some((p) => p.series != null && p.series !== '')
  if (!hasSeries) {
    const rows = data.map((p) => ({ x: p.x ?? '', y: isNum(p.y) ? p.y : Number(p.y) }))
    return { rows, seriesKeys: ['y'], grouped: false }
  }
  const seriesKeys: string[] = []
  const byX = new Map<string, Record<string, unknown>>()
  for (const p of data) {
    const xKey = String(p.x ?? '')
    const s = String(p.series ?? 'series')
    if (!seriesKeys.includes(s)) seriesKeys.push(s)
    let row = byX.get(xKey)
    if (!row) {
      row = { x: p.x ?? '' }
      byX.set(xKey, row)
    }
    row[s] = isNum(p.y) ? p.y : Number(p.y)
  }
  return { rows: Array.from(byX.values()), seriesKeys, grouped: true }
}

function ChartCard({ spec }: { spec: ChartSpec }) {
  const data = Array.isArray(spec.data) ? spec.data.filter((p) => p && typeof p === 'object') : []
  if (data.length === 0) return null

  const type = (spec.type ?? 'bar').toLowerCase()
  const { rows, seriesKeys } = buildSeries(data)

  const axisProps = {
    tick: { fontSize: 11, fill: '#6b7280' },
    stroke: '#9ca3af',
  }
  const xAxisLabel = spec.x_label
    ? { value: spec.x_label, position: 'insideBottom' as const, offset: -4, fontSize: 11, fill: '#6b7280' }
    : undefined
  const yAxisLabel = spec.y_label
    ? { value: spec.y_label, angle: -90, position: 'insideLeft' as const, fontSize: 11, fill: '#6b7280' }
    : undefined

  let chart: React.ReactElement
  if (type === 'line') {
    chart = (
      <LineChart data={rows} margin={{ top: 8, right: 16, bottom: spec.x_label ? 20 : 8, left: spec.y_label ? 12 : 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey="x" {...axisProps} label={xAxisLabel} />
        <YAxis {...axisProps} label={yAxisLabel} />
        <Tooltip />
        {seriesKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
        {seriesKeys.map((k, i) => (
          <Line key={k} type="monotone" dataKey={k} stroke={SERIES_COLORS[i % SERIES_COLORS.length]} strokeWidth={2} dot={{ r: 2 }} />
        ))}
      </LineChart>
    )
  } else if (type === 'scatter') {
    chart = (
      <ScatterChart margin={{ top: 8, right: 16, bottom: spec.x_label ? 20 : 8, left: spec.y_label ? 12 : 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey="x" type="number" {...axisProps} label={xAxisLabel} />
        <YAxis dataKey="y" type="number" {...axisProps} label={yAxisLabel} />
        <ZAxis range={[40, 40]} />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} />
        {seriesKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
        {seriesKeys.map((k, i) => (
          <Scatter key={k} name={k} data={rows.map((r) => ({ x: r.x, y: r[k] }))} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
        ))}
      </ScatterChart>
    )
  } else {
    chart = (
      <BarChart data={rows} margin={{ top: 8, right: 16, bottom: spec.x_label ? 20 : 8, left: spec.y_label ? 12 : 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis dataKey="x" {...axisProps} label={xAxisLabel} />
        <YAxis {...axisProps} label={yAxisLabel} />
        <Tooltip />
        {seriesKeys.length > 1 && <Legend wrapperStyle={{ fontSize: 11 }} />}
        {seriesKeys.map((k, i) => (
          <Bar key={k} dataKey={k} fill={SERIES_COLORS[i % SERIES_COLORS.length]} radius={[3, 3, 0, 0]} />
        ))}
      </BarChart>
    )
  }

  return (
    <figure data-testid="chart-card" className="rounded-lg border border-gray-200 bg-white p-4">
      {spec.title && (
        <figcaption className="mb-2 text-sm font-semibold text-gray-800">{spec.title}</figcaption>
      )}
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {chart}
        </ResponsiveContainer>
      </div>
    </figure>
  )
}

function StatCard({ stat }: { stat: KeyStat }) {
  const deltaStr = stat.delta == null ? '' : String(stat.delta).trim()
  const isDown = /^-|down|decrease|↓/i.test(deltaStr)
  const isUp = deltaStr !== '' && !isDown
  return (
    <div
      data-testid="key-stat"
      className="rounded-lg border border-gray-200 bg-gradient-to-b from-white to-gray-50 p-4"
    >
      {stat.label != null && (
        <div className="text-xs font-medium uppercase tracking-wide text-gray-500">{stat.label}</div>
      )}
      <div className="mt-1 text-2xl font-bold text-gray-900">
        {stat.value == null ? '—' : String(stat.value)}
      </div>
      {deltaStr !== '' && (
        <div
          className={`mt-1 inline-flex items-center gap-1 text-xs font-medium ${
            isDown ? 'text-red-600' : 'text-green-600'
          }`}
        >
          <span aria-hidden="true">{isDown ? '▼' : isUp ? '▲' : ''}</span>
          {deltaStr}
        </div>
      )}
    </div>
  )
}

function TableCard({ table }: { table: TableSpec }) {
  const columns = Array.isArray(table.columns) ? table.columns : []
  const rows = Array.isArray(table.rows) ? table.rows : []
  if (columns.length === 0 && rows.length === 0) return null
  return (
    <div data-testid="table-card" className="overflow-hidden rounded-lg border border-gray-200 bg-white">
      {table.title && (
        <div className="border-b border-gray-200 bg-gray-50 px-4 py-2 text-sm font-semibold text-gray-800">
          {table.title}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          {columns.length > 0 && (
            <thead className="bg-gray-50 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
              <tr>
                {columns.map((c, i) => (
                  <th key={i} className="px-4 py-2">
                    {String(c)}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody className="divide-y divide-gray-100">
            {rows.map((row, ri) => {
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
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/**
 * Renders the rich portion of a completed turn: key-stat callout cards,
 * interactive recharts charts, and summary tables. Every section is defensive —
 * empty or missing arrays render nothing, and odd data never throws.
 */
export function RichOutput({ data }: { data: MessageData }) {
  const charts = Array.isArray(data.charts) ? data.charts : []
  const tables = Array.isArray(data.tables) ? data.tables : []
  const keyStats = Array.isArray(data.key_stats) ? data.key_stats : []

  if (charts.length === 0 && tables.length === 0 && keyStats.length === 0) return null

  return (
    <div data-testid="rich-output" className="mt-4 space-y-4">
      {keyStats.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {keyStats.map((s, i) => (
            <StatCard key={i} stat={s} />
          ))}
        </div>
      )}
      {charts.length > 0 && (
        <div className="space-y-4">
          {charts.map((c, i) => (
            <ChartCard key={i} spec={c} />
          ))}
        </div>
      )}
      {tables.length > 0 && (
        <div className="space-y-4">
          {tables.map((t, i) => (
            <TableCard key={i} table={t} />
          ))}
        </div>
      )}
    </div>
  )
}
