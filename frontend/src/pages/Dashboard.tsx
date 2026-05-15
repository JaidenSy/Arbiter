/**
 * Arbiter — Dashboard page.
 *
 * Landing page showing a high-level overview of gateway activity:
 *   - 4 stat metrics (agents, servers, tool calls, cache hit rate)
 *   - Area chart — real historical data from /stats/history with 7d/24h toggle
 *   - Recent sessions table (last 10, click-through to /sessions)
 */

import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { authClient } from "../api/client";
import type { Agent, DashboardStats, Session, StatsHistoryResponse } from "../api/types";
import UsageStrip from "../components/UsageStrip";
import { useAuth } from "../context/AuthContext";

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchStats = (): Promise<DashboardStats> =>
  authClient.get<DashboardStats>("/stats").then((r) => r.data);

const fetchRecentSessions = (): Promise<Session[]> =>
  authClient
    .get<Session[]>("/sessions", { params: { limit: 10 } })
    .then((r) => r.data);

const fetchAgents = (): Promise<Agent[]> =>
  authClient.get<Agent[]>("/agents").then((r) => r.data);

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function cacheRateColorClass(rate: number): string {
  if (rate >= 0.7) return "text-teal-light";
  if (rate >= 0.4) return "text-warning";
  return "text-error";
}

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function formatDate(): string {
  return new Date().toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}

// ── Stat metric card ──────────────────────────────────────────────────────────

interface StatMetricProps {
  label: string;
  value: string | number;
  valueClass?: string;
  trend?: "up" | "down" | "neutral";
  accent?: "purple" | "teal";
}

function StatMetric({
  label,
  value,
  valueClass = "text-primary",
  trend,
  accent = "purple",
}: StatMetricProps): React.ReactElement {
  return (
    <div className={`flex-1 px-6 py-5 group hover:bg-white/[0.02] transition-all duration-150 relative overflow-hidden`}>
      {/* Subtle corner glow on hover */}
      <div className={`absolute -top-6 -right-6 w-16 h-16 rounded-full blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 ${accent === 'teal' ? 'bg-teal/20' : 'bg-accent/15'}`} />
      <p className="text-muted text-xs font-mono tracking-wider uppercase mb-2 relative">
        {label}
      </p>
      <div className="flex items-end gap-2 relative">
        <p className={`text-3xl font-mono font-light tabular-nums ${valueClass}`}>{value}</p>
        {trend && (
          <span className={`text-xs mb-1 font-semibold ${trend === 'up' ? 'text-success' : trend === 'down' ? 'text-error' : 'text-secondary'}`}>
            {trend === 'up' ? '↑' : trend === 'down' ? '↓' : '—'}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Skeleton shimmer row ──────────────────────────────────────────────────────

function ShimmerRow(): React.ReactElement {
  return (
    <tr className="border-b border-white/[0.05]">
      {[5, 6, 4, 2].map((w, i) => (
        <td key={i} className="py-3 px-4">
          <div className={`h-3 skeleton-shimmer rounded`} style={{ width: `${w * 16}px` }} />
        </td>
      ))}
    </tr>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Dashboard(): React.ReactElement {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [period, setPeriod] = useState<"7d" | "24h">("7d");

  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 30_000,
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery<Session[]>({
    queryKey: ["sessions-recent"],
    queryFn: fetchRecentSessions,
    refetchInterval: 30_000,
  });

  const { data: agents } = useQuery<Agent[]>({
    queryKey: ["agents"],
    queryFn: fetchAgents,
    staleTime: 60_000,
  });

  const { data: history } = useQuery({
    queryKey: ["stats-history", period],
    queryFn: () =>
      authClient
        .get<StatsHistoryResponse>(`/stats/history?period=${period}`)
        .then((r) => r.data),
    refetchInterval: 60_000,
  });

  const chartData = history?.buckets ?? [];
  const allEmpty = chartData.length > 0 && chartData.every((b) => b.tool_calls === 0);

  const agentMap = useMemo(
    () => new Map(agents?.map((a) => [a.id, a.name]) ?? []),
    [agents]
  );

  const cacheRatePct = stats
    ? `${(stats.cache_hit_rate_today * 100).toFixed(1)}%`
    : "—%";

  const userName = user?.email?.split('@')[0] ?? 'there';

  return (
    <div>
      <UsageStrip />
      <div className="p-6 md:p-8 max-w-[1400px] animate-fade-in">

        {/* Greeting header */}
        <div className="mb-8">
          <h1 className="text-primary text-xl font-semibold">
            {getGreeting()}, <span className="gradient-text">{userName}</span>
          </h1>
          <p className="text-secondary text-sm mt-1">{formatDate()}</p>
        </div>

        {/* Stat strip */}
        <div className="flex border border-white/[0.07] rounded-xl mb-6 divide-x divide-white/[0.07] overflow-hidden bg-surface glow-accent">
          <StatMetric
            label="Active Agents"
            value={statsLoading ? "…" : (stats?.agents_count ?? "—")}
            trend="up"
            accent="purple"
          />
          <StatMetric
            label="MCP Servers"
            value={statsLoading ? "…" : (stats?.servers_count ?? "—")}
            accent="purple"
          />
          <StatMetric
            label="Tool Calls Today"
            value={statsLoading ? "…" : (stats?.tool_calls_today ?? "—")}
            trend="up"
            accent="purple"
          />
          <StatMetric
            label="Cache Hit Rate"
            value={statsLoading ? "…" : cacheRatePct}
            valueClass={
              stats
                ? cacheRateColorClass(stats.cache_hit_rate_today)
                : "text-primary"
            }
            trend={stats && stats.cache_hit_rate_today >= 0.5 ? "up" : "down"}
            accent="teal"
          />
        </div>

        {/* Area chart */}
        <div className="border border-white/[0.07] rounded-xl p-6 mb-6 bg-surface">
          <div className="flex items-center justify-between mb-5">
            <div>
              <span className="text-primary text-sm font-semibold">Activity</span>
              <p className="text-secondary text-xs mt-0.5">Tool calls & cache hits over time</p>
            </div>
            <div className="inline-flex border border-white/[0.08] rounded-lg overflow-hidden bg-elevated/50">
              {(["7d", "24h"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-3.5 py-1.5 text-xs font-medium transition-all duration-150 focus:outline-none ${
                    period === p
                      ? "bg-accent/15 text-accent-light border-accent/30"
                      : "text-muted hover:text-secondary hover:bg-elevated/80"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {history === undefined ? (
            <div className="skeleton-shimmer rounded-lg h-[180px] w-full" />
          ) : allEmpty ? (
            <div className="h-[180px] flex flex-col items-center justify-center gap-2">
              <svg className="text-muted" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
              <span className="text-muted text-xs font-mono">
                No activity in the last {period}
              </span>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart
                data={chartData}
                margin={{ top: 4, right: 0, left: -20, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="gradCalls" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7C3AED" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#7C3AED" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradHits" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#14B8A6" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#14B8A6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="rgba(255,255,255,0.04)"
                  vertical={false}
                />
                <XAxis
                  dataKey="label"
                  stroke="transparent"
                  tick={{ fill: "#3A3A4C", fontSize: 11, fontFamily: "monospace" }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke="transparent"
                  tick={{ fill: "#3A3A4C", fontSize: 11, fontFamily: "monospace" }}
                  tickLine={false}
                  axisLine={false}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "#0E0F16",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: 8,
                    fontSize: 12,
                    fontFamily: "monospace",
                  }}
                  labelStyle={{ color: "#7A7A8C", marginBottom: 4 }}
                  itemStyle={{ color: "#F0F0F5" }}
                />
                <Area
                  type="monotone"
                  dataKey="tool_calls"
                  name="Tool Calls"
                  stroke="#7C3AED"
                  strokeWidth={1.5}
                  fill="url(#gradCalls)"
                  dot={false}
                />
                <Area
                  type="monotone"
                  dataKey="cache_hits"
                  name="Cache Hits"
                  stroke="#14B8A6"
                  strokeWidth={1.5}
                  fill="url(#gradHits)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Recent sessions */}
        <div className="border border-white/[0.07] rounded-xl bg-surface overflow-hidden">
          <div className="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between">
            <div>
              <h2 className="text-primary text-sm font-semibold">Recent Sessions</h2>
              <p className="text-secondary text-xs mt-0.5">Latest agent activity</p>
            </div>
          </div>

          {sessionsLoading ? (
            <table className="min-w-full">
              <tbody>
                <ShimmerRow />
                <ShimmerRow />
                <ShimmerRow />
              </tbody>
            </table>
          ) : !sessions || sessions.length === 0 ? (
            <div className="py-16 text-center">
              <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
                <svg className="text-accent-light" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="16" y1="13" x2="8" y2="13"/>
                  <line x1="16" y1="17" x2="8" y2="17"/>
                </svg>
              </div>
              <p className="text-primary text-sm font-medium mb-1">No sessions yet</p>
              <p className="text-secondary text-xs max-w-xs mx-auto">Sessions appear once an agent makes its first tool call through Arbiter.</p>
            </div>
          ) : (
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-white/[0.05]">
                  <th className="py-2.5 px-6 text-left text-xs font-mono text-muted uppercase tracking-wider">Session</th>
                  <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Agent</th>
                  <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Started</th>
                  <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Events</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session, idx) => (
                  <tr
                    key={session.id}
                    className={`cursor-pointer hover:bg-white/[0.025] transition-colors group ${idx % 2 === 0 ? '' : 'bg-white/[0.01]'}`}
                    onClick={() => navigate(`/sessions/${session.id}`)}
                  >
                    <td className="py-3 px-6 text-sm font-mono text-accent-light group-hover:text-white transition-colors">
                      {session.id.slice(0, 8)}
                    </td>
                    <td className="py-3 px-4 text-sm font-mono text-secondary">
                      {agentMap.get(session.agent_id) ?? session.agent_id.slice(0, 8)}
                    </td>
                    <td className="py-3 px-4 text-sm text-secondary">
                      {relativeTime(session.started_at)}
                    </td>
                    <td className="py-3 px-4 text-sm font-mono text-secondary tabular-nums">
                      {session.events?.length ?? 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

      </div>
    </div>
  );
}

export default Dashboard;
