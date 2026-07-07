'use client'

import { useEffect, useState } from 'react'
import { getDailyUsage, type DailyUsage } from '../lib/api'

type QueryCost = {
  prompt_tokens: number | null
  completion_tokens: number | null
  cost_usd: number | null
}

function fmtCost(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '$—'
  return `$${v.toFixed(4)}`
}

function fmtTokens(prompt: number | null | undefined, completion: number | null | undefined): string {
  const p = prompt ?? 0
  const c = completion ?? 0
  if (prompt == null && completion == null) return '— tokens'
  return `${(p + c).toLocaleString()} tokens`
}

/**
 * Bottom cost bar: this query's tokens + cost and today's running daily total.
 * The `refreshKey` prop is bumped by the page after each completed query so the
 * daily total re-fetches from `/usage/daily`.
 */
export function CostBar({ query, refreshKey }: { query: QueryCost | null; refreshKey: number }) {
  const [daily, setDaily] = useState<DailyUsage | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const usage = await getDailyUsage()
        if (!cancelled) setDaily(usage)
      } catch {
        if (!cancelled) setDaily(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [refreshKey])

  return (
    <footer
      data-testid="cost-bar"
      className="flex flex-wrap items-center justify-between gap-2 border-t border-gray-200 bg-white px-4 py-2 text-xs text-gray-600"
    >
      <div className="flex items-center gap-2">
        <span className="font-medium text-gray-700">Usage</span>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span data-testid="query-cost">
          This query:{' '}
          <span className="font-medium text-gray-800">
            {query ? fmtTokens(query.prompt_tokens, query.completion_tokens) : '— tokens'}
          </span>{' '}
          ·{' '}
          <span className="font-medium text-gray-800">{query ? fmtCost(query.cost_usd) : '$—'}</span>
        </span>
        <span data-testid="daily-cost">
          Today:{' '}
          <span className="font-medium text-gray-800">
            {daily ? fmtTokens(daily.prompt_tokens, daily.completion_tokens) : '— tokens'}
          </span>{' '}
          ·{' '}
          <span className="font-medium text-gray-800">{daily ? fmtCost(daily.cost_usd) : '$—'}</span>
        </span>
      </div>
    </footer>
  )
}
