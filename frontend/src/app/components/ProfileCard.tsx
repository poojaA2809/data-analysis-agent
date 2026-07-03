'use client'

import type { Profile, ProfileColumn } from '../lib/api'

// Real Phase-2 profile card. The backend computes the profile shape; we render
// DEFENSIVELY — whatever fields are present are shown, anything missing is
// skipped, and a raw JSON dump is never displayed.

function fmtNum(v: unknown): string {
  if (v == null) return '—'
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) return '—'
    return Math.abs(v) >= 1000 || Number.isInteger(v)
      ? v.toLocaleString()
      : v.toFixed(2)
  }
  return String(v)
}

function columnName(col: ProfileColumn, i: number): string {
  return col.name ?? (col['column'] as string) ?? `col_${i + 1}`
}

function nullPct(col: ProfileColumn, rowCount?: number | null): string {
  if (typeof col.null_pct === 'number') return `${col.null_pct.toFixed(0)}%`
  if (typeof col.null_count === 'number' && rowCount) {
    return `${((col.null_count / rowCount) * 100).toFixed(0)}%`
  }
  return ''
}

function numericSummary(col: ProfileColumn): string | null {
  const s = col.summary
  if (!s || typeof s !== 'object') return null
  const { min, max, mean } = s
  const hasRange = min != null && max != null
  const parts: string[] = []
  if (hasRange) parts.push(`${fmtNum(min)}–${fmtNum(max)}`)
  else if (min != null) parts.push(`min ${fmtNum(min)}`)
  else if (max != null) parts.push(`max ${fmtNum(max)}`)
  if (mean != null) parts.push(`mean ${fmtNum(mean)}`)
  return parts.length > 0 ? parts.join(', ') : null
}

/** Human-readable data-quality chips derived from `profile.quality`. */
function qualityChips(quality: Profile['quality']): string[] {
  if (!quality || typeof quality !== 'object') return []
  const chips: string[] = []
  const missing = Array.isArray(quality.missing_value_columns)
    ? quality.missing_value_columns
    : []
  for (const m of missing) {
    const pct = typeof m.null_pct === 'number' ? ` (${m.null_pct.toFixed(0)}% missing)` : ' missing'
    chips.push(`${m.name ?? 'column'}${pct}`)
  }
  if (typeof quality.duplicate_row_count === 'number' && quality.duplicate_row_count > 0) {
    chips.push(`${quality.duplicate_row_count.toLocaleString()} duplicate rows`)
  }
  const outliers = Array.isArray(quality.outlier_columns) ? quality.outlier_columns : []
  for (const o of outliers) {
    const n = typeof o.outlier_count === 'number' ? o.outlier_count : 0
    chips.push(`${o.name ?? 'column'}: ${n} outlier${n === 1 ? '' : 's'}`)
  }
  return chips
}

function categoricalSummary(col: ProfileColumn): string | null {
  const tv = col.top_values
  if (!Array.isArray(tv) || tv.length === 0) return null
  return tv
    .slice(0, 3)
    .map((t) => `${String(t.value)} (${t.count})`)
    .join(', ')
}

export function ProfileCard({
  filename,
  fileType,
  profile,
}: {
  filename: string
  fileType?: string
  profile: Profile
}) {
  const columns = Array.isArray(profile.columns) ? profile.columns : []
  const rowCount =
    typeof profile.row_count === 'number' ? profile.row_count : undefined
  const colCount =
    typeof profile.column_count === 'number'
      ? profile.column_count
      : columns.length || undefined
  const flags = qualityChips(profile.quality)

  return (
    <div
      data-testid="profile-card"
      className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-900">{filename}</h3>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          {fileType && (
            <span className="rounded bg-gray-100 px-2 py-0.5 uppercase">{fileType}</span>
          )}
          {colCount != null && (
            <span data-testid="profile-colcount">{colCount} columns</span>
          )}
          {rowCount != null && (
            <span data-testid="profile-rowcount">{fmtNum(rowCount)} rows</span>
          )}
        </div>
      </div>

      {profile.summary && (
        <p className="mb-3 text-xs leading-relaxed text-gray-600">{profile.summary}</p>
      )}

      {flags.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2" data-testid="profile-flags">
          {flags.map((f, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-800"
            >
              <span aria-hidden="true">⚠</span>
              {f}
            </span>
          ))}
        </div>
      )}

      {columns.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-500">
                <th className="py-1.5 pr-3 font-medium">Column</th>
                <th className="py-1.5 pr-3 font-medium">Type</th>
                <th className="py-1.5 pr-3 font-medium">Nulls</th>
                <th className="py-1.5 font-medium">Summary</th>
              </tr>
            </thead>
            <tbody>
              {columns.map((col, i) => {
                const pct = nullPct(col, rowCount)
                const nc =
                  typeof col.null_count === 'number' ? col.null_count : null
                const summary =
                  numericSummary(col) ?? categoricalSummary(col) ?? ''
                return (
                  <tr key={i} className="border-b border-gray-100 align-top">
                    <td className="py-1.5 pr-3 font-medium text-gray-800">
                      {columnName(col, i)}
                    </td>
                    <td className="py-1.5 pr-3 text-gray-500">{col.dtype ?? '—'}</td>
                    <td className="py-1.5 pr-3 text-gray-500">
                      {nc != null ? `${fmtNum(nc)}${pct ? ` (${pct})` : ''}` : '—'}
                    </td>
                    <td className="py-1.5 text-gray-600">{summary || '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-xs text-gray-400">
          Profile is being computed for this dataset.
        </p>
      )}
    </div>
  )
}
