/**
 * NexVault — Dashboard page.
 *
 * Landing page showing a high-level overview of gateway activity:
 *   - 4 stat metrics (agents, servers, tool calls, cache hit rate)
 *   - Area chart — real historical data from /stats/history with 7d/24h toggle
 *   - Recent sessions table (last 10, click-through to /sessions)
 */

import React, { useState } from "react";
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
    <div className="flex-1 px-6 py-5">
      <p className="text-muted text-xs font-mono tracking-wider uppercase mb-1">
        {label}
      </p>
      <p className={`text-3xl font-mono font-light ${valueClass}`}>{value}</p>
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

  const cacheRatePct = stats
    ? `${(stats.cache_hit_rate_today * 100).toFixed(1)}%`
    : "—%";

  return (
    <div>
      <UsageStrip />
    <div className="p-8">
      <h1 className="text-primary text-lg font-semibold mb-8">Dashboard</h1>

      {/* Stat strip */}
      <div className="flex border border-white/[0.07] rounded mb-8 divide-x divide-white/[0.07]">
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
      <div className="border border-white/[0.07] p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <span className="text-secondary text-xs uppercase tracking-widest">
            Activity
          </span>
          <div className="inline-flex border border-white/[0.07] rounded overflow-hidden">
            {(["7d", "24h"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 text-xs font-mono transition-colors ${
                  period === p
                    ? "bg-elevated border-white/14 text-primary"
                    : "text-muted hover:text-secondary"
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
        <h2 className="text-secondary text-xs font-mono tracking-wider uppercase mb-4">
          Recent Sessions
        </h2>
        <div className="border-t border-white/[0.07]">
          {sessionsLoading ? (
            <p className="py-4 text-sm text-secondary font-mono">
              Loading sessions…
            </p>
          ) : !sessions || sessions.length === 0 ? (
            <p className="py-4 text-sm text-secondary font-mono">
              No sessions recorded yet.
            </p>
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
                    className="border-b border-white/[0.07] cursor-pointer hover:bg-elevated transition-colors"
                    onClick={() => navigate(`/sessions/${session.id}`)}
                  >
                    <td className="py-2 px-4 text-sm font-mono text-accent-light">
                      {session.id.slice(0, 8)}
                    </td>
                    <td className="py-2 px-4 text-sm font-mono text-secondary">
                      {agents?.find((a) => a.id === session.agent_id)?.name ?? session.agent_id.slice(0, 8)}
                    </td>
                    <td className="py-2 px-4 text-sm text-secondary">
                      {relativeTime(session.started_at)}
                    </td>
                    <td className="py-2 px-4 text-sm font-mono text-secondary">
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
