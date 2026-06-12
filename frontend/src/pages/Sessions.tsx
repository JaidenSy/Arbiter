/**
 * Arbiter — Sessions page.
 *
 * Audit log of all agent sessions.
 *   - Agent filter dropdown
 *   - Sessions table — rows navigate to /sessions/:id for the full trace view
 */

import React, { useState, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { authClient } from "../api/client";
import type { Agent, Page, Session } from "../api/types";
import { Input } from "../components/ui";

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchAgents = (): Promise<Page<Agent>> =>
  authClient.get<Page<Agent>>("/agents").then((r) => r.data);

interface SessionFilters {
  agentId: string;
  toolName: string;
  hasError: string; // ""|"true"|"false"
  fromDate: string;
  toDate: string;
}

const PAGE_SIZE = 20;

const fetchSessions = (filters: SessionFilters, skip: number): Promise<Page<Session>> => {
  const params: Record<string, string> = {};
  if (filters.agentId) params.agent_id = filters.agentId;
  if (filters.toolName) params.tool_name = filters.toolName;
  if (filters.hasError) params.has_error = filters.hasError;
  if (filters.fromDate) params.from_date = new Date(filters.fromDate).toISOString();
  if (filters.toDate) params.to_date = new Date(filters.toDate).toISOString();
  params.skip = String(skip);
  params.limit = String(PAGE_SIZE);
  return authClient.get<Page<Session>>("/sessions", { params }).then((r) => r.data);
};

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

// ── Page ──────────────────────────────────────────────────────────────────────

function Sessions(): React.ReactElement {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [filters, setFilters] = useState<SessionFilters>({
    agentId: searchParams.get("agent_id") ?? "",
    toolName: "",
    hasError: "",
    fromDate: "",
    toDate: "",
  });

  const [page, setPage] = useState(0);

  const setFilter = <K extends keyof SessionFilters>(key: K, value: SessionFilters[K]): void => {
    setPage(0); // reset to first page on filter change
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const { data: agents } = useQuery<Page<Agent>>({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery<Page<Session>>({
    queryKey: ["sessions", filters, page],
    queryFn: () => fetchSessions(filters, page * PAGE_SIZE),
  });

  const agentList = agents?.items ?? [];
  const sessionList = sessions?.items ?? [];
  const totalSessions = sessions?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalSessions / PAGE_SIZE));

  const agentMap = useMemo(
    () => new Map(agentList.map((a) => [a.id, a.name])),
    [agentList]
  );

  const TABLE_COLS = 4;

  return (
    <div className="p-8 animate-fade-in">
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight text-primary">Sessions</h1>
          <p className="text-secondary text-sm mt-1">Full audit log of agent activity and tool calls</p>
        </div>

        {/* Filters */}
        <div className="flex flex-col gap-2 items-end">
          <div className="flex items-center gap-2 flex-wrap">
            <select
              value={filters.agentId}
              onChange={(e) => setFilter("agentId", e.target.value)}
              className="bg-elevated border border-border text-primary text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-border-accent transition-all"
            >
              <option value="">All agents</option>
              {agentList.map((agent) => (
                <option key={agent.id} value={agent.id}>{agent.name}</option>
              ))}
            </select>
            <Input
              type="text"
              placeholder="Tool name"
              value={filters.toolName}
              onChange={(e) => setFilter("toolName", e.target.value)}
              inputClassName="w-36"
            />
            <select
              value={filters.hasError}
              onChange={(e) => setFilter("hasError", e.target.value)}
              className="bg-elevated border border-border text-primary text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-border-accent transition-all"
            >
              <option value="">All results</option>
              <option value="true">Errors only</option>
              <option value="false">No errors</option>
            </select>
            <Input
              type="date"
              value={filters.fromDate}
              onChange={(e) => setFilter("fromDate", e.target.value)}
              inputClassName="w-36"
            />
            <span className="text-muted text-xs">→</span>
            <Input
              type="date"
              value={filters.toDate}
              onChange={(e) => setFilter("toDate", e.target.value)}
              inputClassName="w-36"
            />
          </div>

          {/* Active filter chips */}
          {(filters.agentId || filters.toolName || filters.hasError || filters.fromDate || filters.toDate) && (
            <div className="flex items-center gap-1.5 flex-wrap">
              {filters.agentId && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-accent/10 border border-border-accent text-accent-light">
                  agent: {agentList.find((a) => a.id === filters.agentId)?.name ?? filters.agentId}
                  <button aria-label="Remove agent filter" onClick={() => setFilter("agentId", "")} className="text-accent-light/60 hover:text-accent-light">×</button>
                </span>
              )}
              {filters.toolName && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-accent/10 border border-border-accent text-accent-light">
                  tool: {filters.toolName}
                  <button aria-label="Remove tool filter" onClick={() => setFilter("toolName", "")} className="text-accent-light/60 hover:text-accent-light">×</button>
                </span>
              )}
              {filters.hasError && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-accent/10 border border-border-accent text-accent-light">
                  {filters.hasError === "true" ? "errors only" : "no errors"}
                  <button aria-label="Remove error filter" onClick={() => setFilter("hasError", "")} className="text-accent-light/60 hover:text-accent-light">×</button>
                </span>
              )}
              {filters.fromDate && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-accent/10 border border-border-accent text-accent-light">
                  from: {filters.fromDate}
                  <button aria-label="Remove from-date filter" onClick={() => setFilter("fromDate", "")} className="text-accent-light/60 hover:text-accent-light">×</button>
                </span>
              )}
              {filters.toDate && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-accent/10 border border-border-accent text-accent-light">
                  to: {filters.toDate}
                  <button aria-label="Remove to-date filter" onClick={() => setFilter("toDate", "")} className="text-accent-light/60 hover:text-accent-light">×</button>
                </span>
              )}
              <button
                type="button"
                onClick={() => { setFilters({ agentId: "", toolName: "", hasError: "", fromDate: "", toDate: "" }); setPage(0); }}
                className="text-muted hover:text-secondary text-xs px-2 py-0.5 rounded-lg hover:bg-elevated/60 transition-all"
              >
                Clear all
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Table card */}
      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Session</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Agent</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Started</th>
              <th className="py-3 px-4 text-left text-xs font-mono text-muted uppercase tracking-wider">Events</th>
            </tr>
          </thead>
          <tbody>
            {sessionsLoading ? (
              <>
                {[1, 2, 3, 4].map((i) => (
                  <tr key={i} className="border-b border-border">
                    {[80, 96, 64, 32].map((w, j) => (
                      <td key={j} className="py-3 px-4">
                        <div className="h-3 skeleton-shimmer rounded" style={{ width: w }} />
                      </td>
                    ))}
                  </tr>
                ))}
              </>
            ) : sessionList.length === 0 ? (
              <tr>
                <td colSpan={TABLE_COLS} className="py-20 px-4 text-center">
                  <div className="w-12 h-12 rounded-2xl bg-accent/10 flex items-center justify-center mx-auto mb-4">
                    <svg className="text-accent-light" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                      <line x1="16" y1="13" x2="8" y2="13"/>
                      <line x1="16" y1="17" x2="8" y2="17"/>
                      <polyline points="10 9 9 9 8 9"/>
                    </svg>
                  </div>
                  <p className="text-primary text-sm font-medium mb-1">No sessions recorded yet</p>
                  <p className="text-secondary text-xs max-w-xs mx-auto">Sessions appear here once an agent makes its first tool call.</p>
                </td>
              </tr>
            ) : (
              sessionList.map((session) => (
                <tr
                  key={session.id}
                  className={`border-b border-border cursor-pointer hover:bg-white/[0.025] transition-colors group ${''}`}
                  onClick={() => navigate(`/sessions/${session.id}`)}
                >
                  <td className="py-3 px-4 text-sm font-mono text-accent-light group-hover:text-white transition-colors">
                    {session.id.slice(0, 8)}
                  </td>
                  <td className="py-3 px-4 text-sm font-mono text-secondary">
                    {agentMap.get(session.agent_id) ?? session.agent_id.slice(0, 8)}
                  </td>
                  <td className="py-3 px-4 text-sm text-secondary">
                    {relativeTime(session.started_at)}
                  </td>
                  <td className="py-3 px-4 text-sm font-mono text-secondary tabular-nums">
                    {session.event_count ?? 0}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="border border-border rounded-lg px-3 py-1.5 text-sm text-secondary hover:text-primary disabled:opacity-40 transition-colors"
          >
            ← Previous
          </button>
          <span className="text-secondary text-sm">
            Page {page + 1} of {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="border border-border rounded-lg px-3 py-1.5 text-sm text-secondary hover:text-primary disabled:opacity-40 transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}

export default Sessions;
