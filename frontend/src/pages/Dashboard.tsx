import React, { useState, useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
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
import type { Agent, DashboardStats, HistoryBucket, Page, Session, StatsHistoryResponse } from "../api/types";
import UsageStrip from "../components/UsageStrip";
import { Tile } from "../components/ui/Tile";
import { useAuth } from "../context/AuthContext";
import { CHART_COLORS, CHART_TOOLTIP_STYLE } from "../chartColors";

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchStats = (): Promise<DashboardStats> =>
  authClient.get<DashboardStats>("/stats").then((r) => r.data);

const fetchRecentSessions = (): Promise<Session[]> =>
  authClient
    .get<Page<Session>>("/sessions", { params: { limit: 10 } })
    .then((r) => r.data.items);

const fetchAgents = (): Promise<Page<Agent>> =>
  authClient.get<Page<Agent>>("/agents").then((r) => r.data);

const fetchHistory = (period: string): Promise<StatsHistoryResponse> =>
  authClient.get<StatsHistoryResponse>(`/stats/history?period=${period}`).then((r) => r.data);

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

function errorRateColorClass(rate: number): string {
  if (rate === 0) return "text-success";
  if (rate < 0.05) return "text-warning";
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

function last12(buckets: HistoryBucket[]): HistoryBucket[] {
  return buckets.slice(-12);
}

// ── Skeleton shimmer row ──────────────────────────────────────────────────────

function ShimmerRow(): React.ReactElement {
  return (
    <tr className="border-b border-border">
      {[5, 6, 4, 2].map((w, i) => (
        <td key={i} className="py-3 px-4">
          <div className="h-3 skeleton-shimmer rounded" style={{ width: `${w * 16}px` }} />
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

  const { data: agentsPage } = useQuery<Page<Agent>>({
    queryKey: ["agents"],
    queryFn: fetchAgents,
    staleTime: 60_000,
  });
  const agents = agentsPage?.items;

  // Period-based history for the main activity chart
  const { data: history } = useQuery({
    queryKey: ["stats-history", period],
    queryFn: () => fetchHistory(period),
    refetchInterval: 60_000,
  });

  // Always-24h history for sparklines in metric tiles
  const { data: history24h } = useQuery({
    queryKey: ["stats-history", "24h"],
    queryFn: () => fetchHistory("24h"),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const chartData = history?.buckets ?? [];
  const allEmpty = chartData.length > 0 && chartData.every((b) => b.tool_calls === 0);

  const sparklineBuckets = last12(history24h?.buckets ?? []);
  const sparklineCalls = sparklineBuckets.map((b) => b.tool_calls);
  const sparklineCache = sparklineBuckets.map((b) => b.cache_hit_rate * 100);
  const sparklineErrors = sparklineBuckets.map((b) => b.errors);

  const agentMap = useMemo(
    () => new Map(agents?.map((a) => [a.id, a.name]) ?? []),
    [agents]
  );

  const cacheRatePct = stats
    ? `${(stats.cache_hit_rate_today * 100).toFixed(1)}%`
    : "—%";

  const errorRatePct = stats
    ? `${(stats.error_rate_today * 100).toFixed(1)}%`
    : "—%";

  const userName = user?.email?.split('@')[0] ?? 'there';
  const isNewUser = !statsLoading && stats?.agents_count === 0;

  return (
    <div>
      <UsageStrip />
      <div className="p-6 md:p-8 max-w-[1400px] mx-auto">

        {/* Greeting header */}
        <div className="mb-8 animate-fade-in">
          <h1 className="font-display text-primary text-xl font-semibold tracking-tight">
            {getGreeting()}, <span className="text-accent-light">{userName}</span>
          </h1>
          <p className="text-secondary text-sm mt-1">{formatDate()}</p>
        </div>

        {/* Zero-state CTA for new users */}
        {isNewUser && (
          <div className="mb-6 flex items-center gap-4 bg-accent/5 border border-accent/20 rounded-xl px-5 py-4">
            <div className="w-9 h-9 rounded-xl bg-accent/15 flex items-center justify-center flex-shrink-0">
              <svg className="text-accent-light" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="2" y="3" width="20" height="14" rx="2"/>
                <path d="M8 21h8M12 17v4"/>
                <circle cx="12" cy="10" r="3"/>
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-primary text-sm font-medium">Register your first agent to get started</p>
              <p className="text-secondary text-xs mt-0.5">Agents route tool calls through Arbiter and get a scoped API key.</p>
            </div>
            <Link
              to="/agents"
              className="flex-shrink-0 bg-accent hover:bg-accent-light text-white text-xs font-semibold px-4 py-2 rounded-lg transition-all hover-glow-standard"
            >
              Register Agent →
            </Link>
          </div>
        )}

        {/* ── Bento Row 1: Activity Chart + right-column metric tiles ── */}
        <div className="grid grid-cols-[3fr_1fr] gap-3 mb-3">

          {/* Activity Chart — left column */}
          <div className="border border-border rounded-xl p-6 bg-surface tile-mount stagger-1">
            <div className="flex items-center justify-between mb-5">
              <div>
                <span className="text-primary text-sm font-semibold">Activity</span>
                <p className="text-secondary text-xs mt-0.5">Tool calls & cache hits over time</p>
              </div>
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1.5 text-xs text-muted font-mono">
                    <span className="w-2 h-2 rounded-full bg-accent flex-shrink-0" />
                    Tool Calls
                  </span>
                  <span className="flex items-center gap-1.5 text-xs text-muted font-mono">
                    <span className="w-2 h-2 rounded-full bg-teal flex-shrink-0" />
                    Cache Hits
                  </span>
                </div>
                <div className="inline-flex border border-border rounded-lg overflow-hidden bg-elevated/50">
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
            </div>

            {history === undefined ? (
              <div className="skeleton-shimmer rounded-lg h-[200px] w-full" />
            ) : allEmpty ? (
              <div className="h-[200px] flex flex-col items-center justify-center gap-2">
                <svg className="text-muted" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
                <span className="text-muted text-xs font-mono">
                  No activity in the last {period}
                </span>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart
                  data={chartData}
                  margin={{ top: 4, right: 0, left: -20, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="gradCalls" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_COLORS.amber} stopOpacity={0.35} />
                      <stop offset="95%" stopColor={CHART_COLORS.amber} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gradHits" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_COLORS.teal} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={CHART_COLORS.teal} stopOpacity={0} />
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
                    tick={CHART_TOOLTIP_STYLE.tick}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    stroke="transparent"
                    tick={CHART_TOOLTIP_STYLE.tick}
                    tickLine={false}
                    axisLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={CHART_TOOLTIP_STYLE.content}
                    labelStyle={CHART_TOOLTIP_STYLE.label}
                    itemStyle={CHART_TOOLTIP_STYLE.item}
                  />
                  <Area
                    type="monotone"
                    dataKey="tool_calls"
                    name="Tool Calls"
                    stroke={CHART_COLORS.amber}
                    strokeWidth={1.5}
                    fill="url(#gradCalls)"
                    dot={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="cache_hits"
                    name="Cache Hits"
                    stroke={CHART_COLORS.teal}
                    strokeWidth={1.5}
                    fill="url(#gradHits)"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Right column — stacked metric tiles */}
          <div className="flex flex-col gap-3">
            <Tile
              variant="teal"
              label="Cache Hit Rate"
              value={statsLoading ? "…" : cacheRatePct}
              valueClass={stats ? cacheRateColorClass(stats.cache_hit_rate_today) : ""}
              trend={stats ? (stats.cache_hit_rate_today >= 0.5 ? "up" : "down") : undefined}
              sparklineData={sparklineCache}
              sparklineColor="var(--color-teal)"
              mountDelay={2}
              className="flex-1"
            />
            <Tile
              variant="error"
              label="Error Rate"
              value={statsLoading ? "…" : errorRatePct}
              valueClass={stats ? errorRateColorClass(stats.error_rate_today) : ""}
              trend={stats ? (stats.error_rate_today === 0 ? "up" : stats.error_rate_today > 0.05 ? "down" : "neutral") : undefined}
              sparklineData={sparklineErrors}
              sparklineColor="var(--color-error)"
              mountDelay={3}
              className="flex-1"
            />
          </div>
        </div>

        {/* ── Bento Row 2: Agent, Server, Tool Call tiles ── */}
        <div className="grid grid-cols-[1fr_1fr_2fr] gap-3 mb-6">
          <Tile
            variant="amber"
            label="Active Agents"
            value={statsLoading ? "…" : (stats?.agents_count ?? "—")}
            trend="up"
            to="/agents"
            mountDelay={4}
          />
          <Tile
            variant="default"
            label="MCP Servers"
            value={statsLoading ? "…" : (stats?.servers_count ?? "—")}
            to="/mcp-servers"
            mountDelay={4}
          />
          <Tile
            variant="teal"
            label="Tool Calls Today"
            value={statsLoading ? "…" : (stats?.tool_calls_today?.toLocaleString() ?? "—")}
            trend="up"
            to="/sessions"
            sparklineData={sparklineCalls}
            sparklineColor="var(--color-teal)"
            mountDelay={5}
          />
        </div>

        {/* Recent sessions */}
        <div className="border border-border rounded-xl bg-surface overflow-hidden">
          <div className="px-6 py-4 border-b border-border flex items-center justify-between">
            <div>
              <h2 className="text-primary text-sm font-semibold">Recent Sessions</h2>
              <p className="text-secondary text-xs mt-0.5">Latest agent activity</p>
            </div>
            <Link
              to="/sessions"
              className="text-xs text-muted hover:text-accent-light font-mono transition-colors"
            >
              View all →
            </Link>
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
                <tr className="border-b border-border">
                  <th className="py-2.5 px-6 text-left text-xs font-mono text-muted uppercase tracking-wider">Session</th>
                  <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Agent</th>
                  <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Started</th>
                  <th className="py-2.5 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Events</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr
                    key={session.id}
                    className="cursor-pointer hover:bg-white/[0.025] transition-colors group border-b border-border last:border-0"
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
