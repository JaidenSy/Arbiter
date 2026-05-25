/**
 * Arbiter — UsageStrip component.
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

const SUPPORT_EMAIL: string = import.meta.env.VITE_SUPPORT_EMAIL ?? 'support@arbiterai.dev'

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

// ── Separator ─────────────────────────────────────────────────────────────────

function Sep(): React.ReactElement {
  return <span className="w-px h-3.5 bg-border-strong flex-shrink-0" />
}

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
    <div className="flex items-center gap-3 px-8 py-2 bg-surface border-b border-border text-xs font-mono text-secondary flex-wrap">
      {/* Plan badge */}
      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider ${
        plan === 'enterprise'
          ? 'bg-accent/15 text-accent-light border border-border-accent'
          : plan === 'pro'
          ? 'bg-teal/10 text-teal-light border border-teal/20'
          : 'bg-accent/10 text-accent-light border border-accent/20'
      }`}>
        <span className={`w-1 h-1 rounded-full ${plan === 'enterprise' ? 'bg-accent-light' : plan === 'pro' ? 'bg-teal-light' : 'bg-accent-light'}`} />
        {planLabel}
      </span>

      <Sep />

      <span>
        tool calls:{' '}
        <span className="text-primary">{toolCallsUsed.toLocaleString()}</span>
        <span className="text-muted"> / {formatLimit(limits.toolCalls)}</span>
      </span>

      <Sep />

      <span>
        agents:{' '}
        <span className={isOverAgentLimit ? 'text-error font-semibold' : 'text-primary'}>{agentsCount}</span>
        <span className="text-muted"> / {formatLimit(limits.agents)}</span>
        {isOverAgentLimit && <span className="text-error ml-1">↑ over limit</span>}
      </span>

      <Sep />

      <span>
        cache:{' '}
        <span className={`font-semibold ${stats && stats.cache_hit_rate_today >= 0.5 ? 'text-teal-light' : 'text-primary'}`}>
          {cacheRatePct}
        </span>
      </span>

      {plan === 'free' && (
        <>
          <Sep />
          <Link
            to="/settings#billing"
            className="text-accent-light hover:text-primary transition-colors duration-150 font-medium"
          >
            Upgrade →
          </Link>
        </>
      )}
      {plan === 'enterprise' && (
        <>
          <Sep />
          <a
            href={`mailto:${SUPPORT_EMAIL}?subject=Arbiter Enterprise`}
            className="text-accent-light hover:text-primary transition-colors duration-150 font-medium"
          >
            Contact Sales →
          </a>
        </>
      )}
    </div>
  )
}

export default UsageStrip
