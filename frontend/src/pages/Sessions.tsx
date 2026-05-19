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
import type { Agent, Session } from "../api/types";

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchAgents = (): Promise<Agent[]> =>
  authClient.get<Agent[]>("/agents").then((r) => r.data);

interface SessionFilters {
  agentId: string;
  toolName: string;
  hasError: string; // ""|"true"|"false"
  fromDate: string;
  toDate: string;
}

const fetchSessions = (filters: SessionFilters): Promise<Session[]> => {
  const params: Record<string, string> = {};
  if (filters.agentId) params.agent_id = filters.agentId;
  if (filters.toolName) params.tool_name = filters.toolName;
  if (filters.hasError) params.has_error = filters.hasError;
  if (filters.fromDate) params.from_date = new Date(filters.fromDate).toISOString();
  if (filters.toDate) params.to_date = new Date(filters.toDate).toISOString();
  return authClient.get<Session[]>("/sessions", { params }).then((r) => r.data);
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

  const setFilter = <K extends keyof SessionFilters>(key: K, value: SessionFilters[K]): void => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  };

  const { data: agents } = useQuery<Agent[]>({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery<Session[]>({
    queryKey: ["sessions", filters],
    queryFn: () => fetchSessions(filters),
  });

  const agentMap = useMemo(
    () => new Map(agents?.map((a) => [a.id, a.name]) ?? []),
    [agents]
  );

  const TABLE_COLS = 4;

  return (
    <div className="p-8 animate-fade-in">
      {/* Page header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="gradient-text-purple text-xl font-bold">Sessions</h1>
          <p className="text-secondary text-sm mt-1">Full audit log of agent activity and tool calls</p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={filters.agentId}
            onChange={(e) => setFilter("agentId", e.target.value)}
            className="bg-elevated border border-white/[0.1] text-primary text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-accent/60 transition-all"
          >
            <option value="">All agents</option>
            {agents?.map((agent) => (
              <option key={agent.id} value={agent.id}>{agent.name}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Tool name"
            value={filters.toolName}
            onChange={(e) => setFilter("toolName", e.target.value)}
            className="bg-elevated border border-white/[0.1] text-primary text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-accent/60 transition-all w-36"
          />
          <select
            value={filters.hasError}
            onChange={(e) => setFilter("hasError", e.target.value)}
            className="bg-elevated border border-white/[0.1] text-primary text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-accent/60 transition-all"
          >
            <option value="">All results</option>
            <option value="true">Errors only</option>
            <option value="false">No errors</option>
          </select>
          <input
            type="date"
            value={filters.fromDate}
            onChange={(e) => setFilter("fromDate", e.target.value)}
            className="bg-elevated border border-white/[0.1] text-secondary text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-accent/60 transition-all"
          />
          <span className="text-muted text-xs">→</span>
          <input
            type="date"
            value={filters.toDate}
            onChange={(e) => setFilter("toDate", e.target.value)}
            className="bg-elevated border border-white/[0.1] text-secondary text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-accent/60 transition-all"
          />
          {(filters.agentId || filters.toolName || filters.hasError || filters.fromDate || filters.toDate) && (
            <button
              type="button"
              onClick={() => setFilters({ agentId: "", toolName: "", hasError: "", fromDate: "", toDate: "" })}
              className="text-muted hover:text-secondary text-xs px-2 py-1.5 rounded-lg hover:bg-elevated/60 transition-all"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Table card */}
      <div className="bg-surface border border-white/[0.07] rounded-xl overflow-hidden">
        <table className="min-w-full">
          <thead>
            <tr className="border-b border-white/[0.06]">
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
                  <tr key={i} className="border-b border-white/[0.05]">
                    {[80, 96, 64, 32].map((w, j) => (
                      <td key={j} className="py-3 px-4">
                        <div className="h-3 skeleton-shimmer rounded" style={{ width: w }} />
                      </td>
                    ))}
                  </tr>
                ))}
              </>
            ) : !sessions || sessions.length === 0 ? (
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
              sessions.map((session, idx) => (
                <tr
                  key={session.id}
                  className={`border-b border-white/[0.05] cursor-pointer hover:bg-white/[0.025] transition-colors group ${idx % 2 === 1 ? 'bg-white/[0.01]' : ''}`}
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
                    {session.events?.length ?? 0}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Sessions;
