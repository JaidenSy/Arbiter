/**
 * NexusAI — Dashboard page.
 *
 * Landing page showing a high-level overview of gateway activity:
 *   - 4 stat metrics (agents, servers, tool calls, cache hit rate)
 *   - Area chart — mock 7-day series derived from current stats
 *   - Recent sessions table (last 10, click-through to /sessions)
 */

import React from "react";
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
import { apiClient } from "../api/client";
import type { DashboardStats, Session } from "../api/types";

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchStats = (): Promise<DashboardStats> =>
  apiClient.get<DashboardStats>("/stats").then((r) => r.data);

const fetchRecentSessions = (): Promise<Session[]> =>
  apiClient
    .get<Session[]>("/sessions", { params: { limit: 10 } })
    .then((r) => r.data);

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Generate mock 7-day time-series seeded from real current-day stats. */
function buildMockChartData(
  stats: DashboardStats,
): Array<{ day: string; rate: number; calls: number }> {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const todayRate = stats.cache_hit_rate_today * 100;
  const todayCalls = stats.tool_calls_today;

  return days.map((day, i) => {
    const jitter = Math.sin(i * 1.8) * 0.15 + Math.cos(i) * 0.08;
    const rate = Math.min(100, Math.max(0, todayRate + jitter * 100));
    const calls = Math.max(
      0,
      Math.round(todayCalls + jitter * todayCalls * 0.5),
    );
    return { day, rate: parseFloat(rate.toFixed(1)), calls };
  });
}

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

  const chartData = stats ? buildMockChartData(stats) : [];

  const cacheRatePct = stats
    ? `${(stats.cache_hit_rate_today * 100).toFixed(1)}%`
    : "—%";

  return (
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
        <h2 className="text-secondary text-xs font-mono tracking-wider uppercase mb-4">
          Cache Hit Rate — 7 days
        </h2>
        {statsLoading ? (
          <div className="h-48 flex items-center justify-center text-secondary text-sm font-mono">
            Loading chart…
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={192}>
            <AreaChart
              data={chartData}
              margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
            >
              <defs>
                <linearGradient id="colorGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#7c3aed" stopOpacity={0.6} />
                  <stop offset="95%" stopColor="#7c3aed" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="rgba(255,255,255,0.04)"
              />
              <XAxis
                dataKey="day"
                stroke="#444"
                tick={{ fill: '#888', fontSize: 11, fontFamily: 'monospace' }}
              />
              <YAxis
                domain={[0, 100]}
                unit="%"
                stroke="#444"
                tick={{ fill: '#888', fontSize: 11, fontFamily: 'monospace' }}
              />
              <Tooltip
                contentStyle={{
                  background: '#111111',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 4,
                  color: '#efefef',
                  fontSize: 12,
                  fontFamily: 'monospace',
                }}
                formatter={(v: number) => [`${v}%`, "Hit Rate"]}
              />
              <Area
                type="monotone"
                dataKey="rate"
                stroke="#7c3aed"
                strokeWidth={1.5}
                fill="url(#colorGradient)"
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
                    onClick={() =>
                      navigate(`/sessions?agent_id=${session.agent_id}`)
                    }
                  >
                    <td className="py-2 px-4 text-sm font-mono text-accent-light">
                      {session.id.slice(0, 8)}
                    </td>
                    <td className="py-2 px-4 text-sm font-mono text-secondary">
                      {session.agent_id.slice(0, 8)}
                    </td>
                    <td className="py-2 px-4 text-sm text-secondary">
                      {relativeTime(session.started_at)}
                    </td>
                    <td className="py-2 px-4 text-sm font-mono text-secondary">
                      {session.events?.length ?? "—"}
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
