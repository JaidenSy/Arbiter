import React, { useState, useMemo } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
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
import type { Agent, CostStats, DashboardStats, HistoryBucket, MCPServer, Page, Session, StatsHistoryResponse, UsageSummary } from "../api/types";
import { useAuth } from "../context/AuthContext";
import UsageStrip from "../components/UsageStrip";
import { Tile } from "../components/ui/Tile";
import { CHART_COLORS, CHART_TOOLTIP_STYLE } from "../chartColors";

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchStats = (agentId?: string, serverName?: string): Promise<DashboardStats> => {
  const params: Record<string, string> = {};
  if (agentId) params.agent_id = agentId;
  if (serverName) params.server_name = serverName;
  return authClient.get<DashboardStats>("/stats", { params }).then((r) => r.data);
};

const fetchRecentSessions = (): Promise<Session[]> =>
  authClient
    .get<Page<Session>>("/sessions", { params: { limit: 10 } })
    .then((r) => r.data.items);

const fetchAgents = (): Promise<Page<Agent>> =>
  authClient.get<Page<Agent>>("/agents").then((r) => r.data);

const fetchMcpServers = (): Promise<Page<MCPServer>> =>
  authClient.get<Page<MCPServer>>("/mcp-servers").then((r) => r.data);

const fetchHistory = (period: string, agentId?: string, serverName?: string): Promise<StatsHistoryResponse> => {
  const params: Record<string, string> = { period };
  if (agentId) params.agent_id = agentId;
  if (serverName) params.server_name = serverName;
  return authClient.get<StatsHistoryResponse>("/stats/history", { params }).then((r) => r.data);
};

const fetchUsageSummary = (): Promise<UsageSummary> =>
  authClient.get<UsageSummary>("/stats/usage/summary").then((r) => r.data);

const fetchCostStats = (): Promise<CostStats> =>
  authClient.get<CostStats>("/stats/cost").then((r) => r.data);

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

function latencyColorClass(ms: number): string {
  if (ms < 300) return "text-teal-light";
  if (ms < 1000) return "text-warning";
  return "text-error";
}

function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function last12(buckets: HistoryBucket[]): HistoryBucket[] {
  return buckets.slice(-12);
}

function firstDayOfNextMonth(): string {
  const now = new Date();
  const next = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  return next.toLocaleDateString("en-US", { month: "short", day: "numeric" });
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

// ── Filter bar ────────────────────────────────────────────────────────────────

interface FilterBarProps {
  agents: Agent[];
  servers: MCPServer[];
  selectedAgentId: string;
  selectedServerName: string;
  onAgentChange: (v: string) => void;
  onServerChange: (v: string) => void;
}

function FilterBar({ agents, servers, selectedAgentId, selectedServerName, onAgentChange, onServerChange }: FilterBarProps): React.ReactElement {
  const hasFilter = selectedAgentId !== "" || selectedServerName !== "";
  return (
    <div className="flex items-center gap-2 mb-4">
      <select
        value={selectedAgentId}
        onChange={(e) => onAgentChange(e.target.value)}
        className="text-xs font-mono bg-elevated border border-border rounded-lg px-3 py-1.5 text-secondary focus:outline-none focus:border-accent/50 transition-colors"
      >
        <option value="">All agents</option>
        {agents.map((a) => (
          <option key={a.id} value={a.id}>{a.name}</option>
        ))}
      </select>
      <select
        value={selectedServerName}
        onChange={(e) => onServerChange(e.target.value)}
        className="text-xs font-mono bg-elevated border border-border rounded-lg px-3 py-1.5 text-secondary focus:outline-none focus:border-accent/50 transition-colors"
      >
        <option value="">All servers</option>
        {servers.map((s) => (
          <option key={s.id} value={s.name}>{s.name}</option>
        ))}
      </select>
      {hasFilter && (
        <button
          onClick={() => { onAgentChange(""); onServerChange(""); }}
          className="text-xs font-mono text-muted hover:text-error transition-colors px-2 py-1.5"
        >
          ✕ Clear
        </button>
      )}
      {hasFilter && (
        <span className="text-xs font-mono text-accent-light bg-accent/10 border border-accent/20 rounded px-2 py-1">
          filtered
        </span>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Dashboard(): React.ReactElement {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isPro = user?.org_plan !== "free";
  const [searchParams, setSearchParams] = useSearchParams();
  const [period, setPeriod] = useState<"7d" | "24h">("7d");

  // Persist filter in URL so Agents page can deep-link here with ?agent_id=...
  const selectedAgentId = searchParams.get("agent_id") ?? "";
  const selectedServerName = searchParams.get("server_name") ?? "";

  const setAgentId = (v: string) => setSearchParams((p) => { const n = new URLSearchParams(p); if (v) n.set("agent_id", v); else n.delete("agent_id"); return n; });
  const setServerName = (v: string) => setSearchParams((p) => { const n = new URLSearchParams(p); if (v) n.set("server_name", v); else n.delete("server_name"); return n; });

  const { data: stats, isLoading: statsLoading } = useQuery<DashboardStats>({
    queryKey: ["stats", selectedAgentId, selectedServerName],
    queryFn: () => fetchStats(selectedAgentId || undefined, selectedServerName || undefined),
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
  const agents = agentsPage?.items ?? [];

  const { data: mcpServersPage } = useQuery<Page<MCPServer>>({
    queryKey: ["mcp-servers"],
    queryFn: fetchMcpServers,
    staleTime: 60_000,
  });
  const mcpServers = mcpServersPage?.items ?? [];

  const { data: history } = useQuery({
    queryKey: ["stats-history", period, selectedAgentId, selectedServerName],
    queryFn: () => fetchHistory(period, selectedAgentId || undefined, selectedServerName || undefined),
    refetchInterval: 60_000,
  });

  const { data: history24h } = useQuery({
    queryKey: ["stats-history", "24h"],
    queryFn: () => fetchHistory("24h"),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const { data: usageSummary } = useQuery<UsageSummary>({
    queryKey: ["usage-summary"],
    queryFn: fetchUsageSummary,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const { data: costStats } = useQuery<CostStats>({
    queryKey: ["cost-stats"],
    queryFn: fetchCostStats,
    enabled: isPro,
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: false,
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

  const isNewUser = !statsLoading && stats?.agents_count === 0;

  // ── Monthly quota derived values ──────────────────────────────────────────
  const quotaUsed = usageSummary?.tool_calls_month ?? 0;
  const quotaLimit = usageSummary?.tool_calls_month_limit ?? null;
  const quotaPct = quotaLimit !== null ? Math.min(quotaUsed / quotaLimit, 1) : 0;
  const isNearLimit = quotaLimit !== null && quotaPct >= 0.8;
  const isOverLimit = quotaLimit !== null && quotaUsed >= quotaLimit;
  const quotaBarColor = isOverLimit ? "bg-error" : isNearLimit ? "bg-warning" : "bg-accent";
  const resetDate = firstDayOfNextMonth();

  const hasFilter = selectedAgentId !== "" || selectedServerName !== "";

  return (
    <div>
      <UsageStrip />
      <div className="p-6 md:p-8 max-w-[1400px] mx-auto">

        {/* Page title */}
        <div className="mb-6">
          <h1 className="font-display text-primary text-xl font-semibold tracking-tight">Overview</h1>
        </div>

        {/* Filter bar */}
        <FilterBar
          agents={agents}
          servers={mcpServers}
          selectedAgentId={selectedAgentId}
          selectedServerName={selectedServerName}
          onAgentChange={setAgentId}
          onServerChange={setServerName}
        />

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
                <p className="text-secondary text-xs mt-0.5">
                  Tool calls & cache hits over time
                  {hasFilter && <span className="ml-1 text-accent-light">(filtered)</span>}
                </p>
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
                    stroke="var(--color-border)"
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
        <div className="grid grid-cols-[1fr_1fr_2fr] gap-3 mb-3">
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

        {/* ── Bento Row 3: Latency tiles ── */}
        <div className="grid grid-cols-3 gap-3 mb-3">
          <Tile
            variant="default"
            label="p50 Latency"
            value={statsLoading ? "…" : fmtMs(stats?.latency_p50_ms)}
            valueClass={stats?.latency_p50_ms != null ? latencyColorClass(stats.latency_p50_ms) : "text-muted"}
            mountDelay={6}
          />
          <Tile
            variant="default"
            label="p95 Latency"
            value={statsLoading ? "…" : fmtMs(stats?.latency_p95_ms)}
            valueClass={stats?.latency_p95_ms != null ? latencyColorClass(stats.latency_p95_ms) : "text-muted"}
            mountDelay={6}
          />
          <Tile
            variant="default"
            label="p99 Latency"
            value={statsLoading ? "…" : fmtMs(stats?.latency_p99_ms)}
            valueClass={stats?.latency_p99_ms != null ? latencyColorClass(stats.latency_p99_ms) : "text-muted"}
            mountDelay={6}
          />
        </div>

        {/* ── Bento Row 4: Cost tiles (Pro+) ── */}
        {isPro && (
          <div className="grid grid-cols-2 gap-3 mb-3">
            <Tile
              variant="amber"
              label="Cost This Month"
              value={costStats != null ? `$${costStats.cost_this_month_usd.toFixed(4)}` : "—"}
              mountDelay={7}
            />
            <Tile
              variant="teal"
              label="Saved by Cache"
              value={costStats != null ? `$${costStats.cost_saved_by_cache_usd.toFixed(4)}` : "—"}
              trend="up"
              mountDelay={7}
            />
          </div>
        )}

        {/* ── Slowest Tools table (shown when there's data) ── */}
        {stats && stats.slowest_tools.length > 0 && (
          <div className="border border-border rounded-xl bg-surface overflow-hidden mb-3 tile-mount stagger-5">
            <div className="px-5 py-3.5 border-b border-border">
              <span className="text-primary text-sm font-semibold">Slowest Tools Today</span>
              <p className="text-secondary text-xs mt-0.5">By average call duration</p>
            </div>
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 px-5 text-left text-xs font-mono text-muted uppercase tracking-wider">Tool</th>
                  <th className="py-2 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Server</th>
                  <th className="py-2 px-4 text-right text-xs font-mono text-muted uppercase tracking-wider">Avg</th>
                  <th className="py-2 px-4 text-right text-xs font-mono text-muted uppercase tracking-wider">Calls</th>
                </tr>
              </thead>
              <tbody>
                {stats.slowest_tools.map((t, i) => (
                  <tr key={i} className="border-b border-border last:border-0 hover:bg-white/[0.015] transition-colors">
                    <td className="py-2.5 px-5 text-sm font-mono text-primary">{t.tool_name}</td>
                    <td className="py-2.5 px-4 text-xs font-mono text-muted">{t.server_name ?? "—"}</td>
                    <td className={`py-2.5 px-4 text-sm font-mono text-right tabular-nums ${latencyColorClass(t.avg_duration_ms)}`}>
                      {fmtMs(t.avg_duration_ms)}
                    </td>
                    <td className="py-2.5 px-4 text-sm font-mono text-secondary text-right tabular-nums">{t.call_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Monthly Quota Card ── */}
        <div className="border border-border rounded-xl p-5 bg-surface tile-mount stagger-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="text-primary text-sm font-semibold">Monthly Usage</span>
              <p className="text-secondary text-xs mt-0.5">
                Resets {resetDate}
              </p>
            </div>
            <span className={`text-sm font-mono tabular-nums ${isOverLimit ? "text-error" : isNearLimit ? "text-warning" : "text-primary"}`}>
              {quotaUsed.toLocaleString()}
              {" / "}
              {quotaLimit !== null ? quotaLimit.toLocaleString() : "∞"}
              {" calls"}
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-elevated overflow-hidden">
            {quotaLimit !== null ? (
              <div
                className={`h-full rounded-full transition-all duration-500 ${quotaBarColor}`}
                style={{ width: `${quotaPct * 100}%` }}
              />
            ) : (
              <div className="h-full rounded-full bg-accent/30 w-full" />
            )}
          </div>
          {isNearLimit && !isOverLimit && (
            <p className="text-warning text-xs mt-2 font-mono">
              Approaching monthly limit — consider{" "}
              <Link to="/settings?tab=billing" className="underline hover:text-primary transition-colors">
                upgrading to Pro
              </Link>
              .
            </p>
          )}
          {isOverLimit && (
            <p className="text-error text-xs mt-2 font-mono">
              Monthly quota exceeded — tool calls are paused until {resetDate}.
            </p>
          )}
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
                      {session.event_count ?? session.events?.length ?? 0}
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
