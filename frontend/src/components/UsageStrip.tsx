/**
 * NexusAI — UsageStrip component.
 *
 * Horizontal strip shown at the top of Dashboard when user is authenticated via JWT.
 * Displays: plan name · tool calls used / limit · agents count / limit · cache hit rate
 * Includes an "Upgrade →" link to /settings#billing.
 */

import React from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '../context/AuthContext'
import { authClient } from '../api/client'
import type { DashboardStats } from '../api/types'

// ── Plan limit constants (mirrors backend plan_limits.py) ────────────────────

const PLAN_LIMITS: Record<string, { agents: number | null; toolCalls: number | null }> = {
  free:       { agents: 3,  toolCalls: 1_000 },
  pro:        { agents: 25, toolCalls: 100_000 },
  enterprise: { agents: null, toolCalls: null },
}

function formatLimit(value: number | null): string {
  if (value === null) return '∞'
  return value.toLocaleString()
}

// ── Fetchers ─────────────────────────────────────────────────────────────────

interface UsageSummary {
  tool_calls_month: number
}

const fetchUsageSummary = (): Promise<UsageSummary> =>
  authClient.get<UsageSummary>('/stats/usage/summary').then((r) => r.data)

const fetchStats = (): Promise<DashboardStats> =>
  authClient.get<DashboardStats>('/stats').then((r) => r.data)

// ── Component ─────────────────────────────────────────────────────────────────

function UsageStrip(): React.ReactElement | null {
  const { user } = useAuth()

  const { data: stats } = useQuery<DashboardStats>({
    queryKey: ['stats'],
    queryFn: fetchStats,
    staleTime: 30_000,
  })

  const { data: usage } = useQuery<UsageSummary>({
    queryKey: ['usage-summary'],
    queryFn: fetchUsageSummary,
    staleTime: 60_000,
  })

  // Only render for JWT-authenticated users
  if (!user) return null

  const plan = user.org_plan ?? 'free'
  const limits = PLAN_LIMITS[plan] ?? PLAN_LIMITS.free

  const toolCallsUsed = usage?.tool_calls_month ?? stats?.tool_calls_today ?? 0
  const agentsCount = stats?.agents_count ?? 0
  const isOverAgentLimit = limits.agents !== null && agentsCount > limits.agents
  const cacheRatePct = stats
    ? `${(stats.cache_hit_rate_today * 100).toFixed(0)}%`
    : '—'

  const planLabel = plan.charAt(0).toUpperCase() + plan.slice(1)

  return (
    <div className="flex items-center gap-4 px-8 py-2.5 bg-surface border-b border-white/[0.07] text-xs font-mono text-secondary flex-wrap">
      <span className="text-accent-light font-semibold">{planLabel} Plan</span>
      <span className="text-white/20">•</span>
      <span>
        tool calls:{' '}
        <span className="text-primary">{toolCallsUsed.toLocaleString()}</span>
        {' / '}
        <span>{formatLimit(limits.toolCalls)}</span>
      </span>
      <span className="text-white/20">•</span>
      <span>
        agents:{' '}
        <span className={isOverAgentLimit ? 'text-red-400 font-semibold' : 'text-primary'}>{agentsCount}</span>
        {' / '}
        <span>{formatLimit(limits.agents)}</span>
        {isOverAgentLimit && <span className="text-red-400 ml-1">↑ over limit</span>}
      </span>
      <span className="text-white/20">•</span>
      <span>
        cache hit rate: <span className="text-primary">{cacheRatePct}</span>
      </span>
      {plan !== 'enterprise' && (
        <>
          <span className="text-white/20">•</span>
          <Link
            to="/settings#billing"
            className="text-accent-light hover:text-white transition-colors"
          >
            Upgrade →
          </Link>
        </>
      )}
    </div>
  )
}

export default UsageStrip
