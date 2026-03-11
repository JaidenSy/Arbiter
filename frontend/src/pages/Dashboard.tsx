/**
 * NexusAI — Dashboard page.
 *
 * Landing page showing a high-level overview of gateway activity:
 *   - 4 stat cards (agents, servers, tool calls, cache hit rate)
 *   - Area chart — mock 7-day series derived from current stats
 *   - Recent sessions table (last 10, click-through to /sessions)
 */

import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { apiClient } from '../api/client'
import type { DashboardStats, Session } from '../api/types'

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchStats = (): Promise<DashboardStats> =>
  apiClient.get<DashboardStats>('/stats').then((r) => r.data)

const fetchRecentSessions = (): Promise<Session[]> =>
  apiClient.get<Session[]>('/sessions', { params: { limit: 10 } }).then((r) => r.data)

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Generate mock 7-day time-series seeded from real current-day stats. */
function buildMockChartData(stats: DashboardStats): Array<{ day: string; rate: number; calls: number }> {
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  const todayRate = stats.cache_hit_rate_today * 100
  const todayCalls = stats.tool_calls_today

  return days.map((day, i) => {
    // Vary each day by ±15 pp around today's values to produce a realistic curve
    const jitter = (Math.sin(i * 1.8) * 0.15 + Math.cos(i) * 0.08)
    const rate = Math.min(100, Math.max(0, todayRate + jitter * 100))
    const calls = Math.max(0, Math.round(todayCalls + jitter * todayCalls * 0.5))
    return { day, rate: parseFloat(rate.toFixed(1)), calls }
  })
}

/** Format a relative timestamp (e.g. "3 min ago"). */
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

/** Color class for cache hit rate value. */
function cacheRateColorClass(rate: number): string {
  if (rate >= 0.7) return 'text-green-600'
  if (rate >= 0.4) return 'text-yellow-600'
  return 'text-red-600'
}

// ── Stat card ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: string | number
  valueClass?: string
}

function StatCard({ label, value, valueClass = 'text-gray-900' }: StatCardProps): React.ReactElement {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${valueClass}`}>{value}</p>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Dashboard(): React.ReactElement {
  const navigate = useNavigate()

  const {
    data: stats,
    isLoading: statsLoading,
  } = useQuery<DashboardStats>({
    queryKey: ['stats'],
    queryFn: fetchStats,
    refetchInterval: 30_000,
  })

  const {
    data: sessions,
    isLoading: sessionsLoading,
  } = useQuery<Session[]>({
    queryKey: ['sessions-recent'],
    queryFn: fetchRecentSessions,
    refetchInterval: 30_000,
  })

  const chartData = stats ? buildMockChartData(stats) : []

  const cacheRatePct = stats
    ? `${(stats.cache_hit_rate_today * 100).toFixed(1)}%`
    : '—%'

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Active Agents"
          value={statsLoading ? '…' : (stats?.agents_count ?? '—')}
        />
        <StatCard
          label="MCP Servers"
          value={statsLoading ? '…' : (stats?.servers_count ?? '—')}
        />
        <StatCard
          label="Tool Calls Today"
          value={statsLoading ? '…' : (stats?.tool_calls_today ?? '—')}
        />
        <StatCard
          label="Cache Hit Rate"
          value={statsLoading ? '…' : cacheRatePct}
          valueClass={
            stats
              ? cacheRateColorClass(stats.cache_hit_rate_today)
              : 'text-indigo-600'
          }
        />
      </div>

      {/* Area chart */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Cache Hit Rate (7 days)</h2>
        {statsLoading ? (
          <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
            Loading chart…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={192}>
            <AreaChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="cacheGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="day" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 12 }} />
              <Tooltip formatter={(v: number) => [`${v}%`, 'Hit Rate']} />
              <Area
                type="monotone"
                dataKey="rate"
                stroke="#6366f1"
                strokeWidth={2}
                fill="url(#cacheGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Recent sessions table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Recent Sessions</h2>
        </div>

        {sessionsLoading ? (
          <div className="p-6 text-sm text-gray-400">Loading sessions…</div>
        ) : !sessions || sessions.length === 0 ? (
          <div className="p-6 text-sm text-gray-400">No sessions recorded yet.</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Session</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Agent</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Started</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Events</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sessions.map((session) => (
                <tr
                  key={session.id}
                  className="cursor-pointer hover:bg-gray-50 transition-colors"
                  onClick={() => navigate(`/sessions?agent_id=${session.agent_id}`)}
                >
                  <td className="px-6 py-4 text-sm font-mono text-gray-900">
                    {session.id.slice(0, 8)}
                  </td>
                  <td className="px-6 py-4 text-sm font-mono text-gray-600">
                    {session.agent_id.slice(0, 8)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {relativeTime(session.started_at)}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {session.events?.length ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

export default Dashboard
