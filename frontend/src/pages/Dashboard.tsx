/**
 * NexVault — Dashboard page.
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

/** Format a relative timestamp (e.g. "3 min ago"). */
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** Color class for cache hit rate value. */
function cacheRateColorClass(rate: number): string {
  if (rate >= 0.7) return "text-green-400";
  if (rate >= 0.4) return "text-yellow-400";
  return "text-red-400";
}

// ── Stat metric ───────────────────────────────────────────────────────────────

interface StatMetricProps {
  label: string;
  value: string | number;
  valueClass?: string;
}

function StatMetric({
  label,
  value,
  valueClass = "text-primary",
}: StatMetricProps): React.ReactElement {
  return (
    <div className="flex-1 px-6 py-5 group hover:bg-elevated/60 transition-colors">
      <p className="text-muted text-xs font-mono tracking-wider uppercase mb-2">
        {label}
      </p>
      <p className={`text-3xl font-mono font-light tabular-nums ${valueClass}`}>{value}</p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Dashboard(): React.ReactElement {
  const navigate = useNavigate();
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

  // Memoised agent lookup map to avoid O(n*m) find() on every render
  const agentMap = useMemo(
    () => new Map(agents?.map((a) => [a.id, a.name]) ?? []),
    [agents]
  );

  const cacheRatePct = stats
    ? `${(stats.cache_hit_rate_today * 100).toFixed(1)}%`
    : "—%";

  return (
    <div>
      <UsageStrip />
    <div className="p-6 md:p-8 max-w-[1400px]">
      <h1 className="text-primary text-lg font-semibold mb-6">Dashboard</h1>

      {/* Stat strip */}
      <div className="flex border border-white/[0.07] rounded-lg mb-6 divide-x divide-white/[0.07] overflow-hidden">
        <StatMetric
          label="Active Agents"
          value={statsLoading ? "…" : (stats?.agents_count ?? "—")}
        />
        <StatMetric
          label="MCP Servers"
          value={statsLoading ? "…" : (stats?.servers_count ?? "—")}
        />
        <StatMetric
          label="Tool Calls Today"
          value={statsLoading ? "…" : (stats?.tool_calls_today ?? "—")}
        />
        <StatMetric
          label="Cache Hit Rate"
          value={statsLoading ? "…" : cacheRatePct}
          valueClass={
            stats
              ? cacheRateColorClass(stats.cache_hit_rate_today)
              : "text-primary"
          }
        />
      </div>

      {/* Area chart */}
      <div className="border border-white/[0.07] rounded-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <span className="text-secondary text-xs uppercase tracking-widest font-mono">
            Activity
          </span>
          <div className="inline-flex border border-white/[0.07] rounded-md overflow-hidden">
            {(["7d", "24h"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 text-xs font-mono transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-accent ${
                  period === p
                    ? "bg-elevated text-primary"
                    : "text-muted hover:text-secondary hover:bg-elevated/50"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {history === undefined ? (
          <div className="animate-pulse bg-elevated rounded h-[180px] w-full" />
        ) : allEmpty ? (
          <div className="h-[180px] flex items-center justify-center">
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
                  <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradHits" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
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
                tick={{ fill: "#444", fontSize: 11, fontFamily: "monospace" }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="transparent"
                tick={{ fill: "#444", fontSize: 11, fontFamily: "monospace" }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  background: "#111",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 4,
                  fontSize: 12,
                  fontFamily: "monospace",
                }}
                labelStyle={{ color: "#888", marginBottom: 4 }}
                itemStyle={{ color: "#efefef" }}
              />
              <Area
                type="monotone"
                dataKey="tool_calls"
                name="Tool Calls"
                stroke="#7c3aed"
                strokeWidth={1.5}
                fill="url(#gradCalls)"
                dot={false}
              />
              <Area
                type="monotone"
                dataKey="cache_hits"
                name="Cache Hits"
                stroke="#22c55e"
                strokeWidth={1.5}
                fill="url(#gradHits)"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Recent sessions table */}
      <div>
        <h2 className="text-secondary text-xs font-mono tracking-wider uppercase mb-3">
          Recent Sessions
        </h2>
        <div className="border-t border-white/[0.07]">
          {sessionsLoading ? (
            <div className="space-y-2 py-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="animate-pulse flex gap-4 px-4 py-2">
                  <div className="h-3 bg-elevated rounded w-20" />
                  <div className="h-3 bg-elevated rounded w-24" />
                  <div className="h-3 bg-elevated rounded w-16" />
                  <div className="h-3 bg-elevated rounded w-8" />
                </div>
              ))}
            </div>
          ) : !sessions || sessions.length === 0 ? (
            <div className="py-12 text-center">
              <svg className="mx-auto mb-3 text-muted" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
              <p className="text-secondary text-sm font-mono mb-1">No sessions yet.</p>
              <p className="text-muted text-xs">Sessions appear once an agent makes its first tool call.</p>
            </div>
          ) : (
            <table className="min-w-full">
              <thead>
                <tr>
                  <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                    Session
                  </th>
                  <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                    Agent
                  </th>
                  <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                    Started
                  </th>
                  <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">
                    Events
                  </th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr
                    key={session.id}
                    className="border-b border-white/[0.07] cursor-pointer hover:bg-elevated/70 transition-colors group"
                    onClick={() => navigate(`/sessions/${session.id}`)}
                  >
                    <td className="py-2.5 px-4 text-sm font-mono text-accent-light group-hover:text-white transition-colors">
                      {session.id.slice(0, 8)}
                    </td>
                    <td className="py-2.5 px-4 text-sm font-mono text-secondary">
                      {agentMap.get(session.agent_id) ?? session.agent_id.slice(0, 8)}
                    </td>
                    <td className="py-2.5 px-4 text-sm text-secondary">
                      {relativeTime(session.started_at)}
                    </td>
                    <td className="py-2.5 px-4 text-sm font-mono text-secondary tabular-nums">
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
    </div>
  );
}

export default Dashboard;
