/**
 * NexusAI — Sessions page.
 *
 * Audit log of all agent sessions and their tool call events.
 *   - Agent filter dropdown
 *   - Sessions table with expandable inline event rows
 *   - Events lazy-loaded per session on row expand
 */

import React, { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import type { Agent, Session, SessionEvent } from "../api/types";

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchAgents = (): Promise<Agent[]> =>
  apiClient.get<Agent[]>("/agents").then((r) => r.data);

const fetchSessions = (agentId: string): Promise<Session[]> =>
  apiClient
    .get<Session[]>("/sessions", {
      params: agentId ? { agent_id: agentId } : undefined,
    })
    .then((r) => r.data);

const fetchSessionEvents = (sessionId: string): Promise<SessionEvent[]> =>
  apiClient
    .get<SessionEvent[]>(`/sessions/${sessionId}/events`)
    .then((r) => r.data);

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

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  return `${ms} ms`;
}

// ── Events sub-table ──────────────────────────────────────────────────────────

interface EventsRowsProps {
  sessionId: string;
  colSpan: number;
}

function EventsRows({
  sessionId,
  colSpan,
}: EventsRowsProps): React.ReactElement {
  const { data: events, isLoading } = useQuery<SessionEvent[]>({
    queryKey: ["events", sessionId],
    queryFn: () => fetchSessionEvents(sessionId),
  });

  if (isLoading) {
    return (
      <tr className="bg-highlight/30 border-b border-white/[0.07]">
        <td colSpan={colSpan} className="pl-8 py-3 text-sm text-secondary font-mono">
          Loading events…
        </td>
      </tr>
    );
  }

  if (!events || events.length === 0) {
    return (
      <tr className="bg-highlight/30 border-b border-white/[0.07]">
        <td colSpan={colSpan} className="pl-8 py-3 text-sm text-secondary font-mono">
          No events recorded for this session.
        </td>
      </tr>
    );
  }

  return (
    <tr className="bg-highlight/30 border-b border-white/[0.07]">
      <td colSpan={colSpan} className="py-0 px-0">
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="pl-8 pr-4 py-2 text-left text-xs font-mono text-muted uppercase tracking-wider w-1/4">
                Tool
              </th>
              <th className="px-4 py-2 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Cache
              </th>
              <th className="px-4 py-2 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Duration
              </th>
              <th className="px-4 py-2 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Error
              </th>
              <th className="px-4 py-2 text-left text-xs font-mono text-muted uppercase tracking-wider">
                Time
              </th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr
                key={event.id}
                className="border-t border-white/[0.04] hover:bg-elevated transition-colors"
              >
                <td className="pl-8 pr-4 py-2 text-xs font-mono text-primary">
                  {event.tool_name}
                </td>
                <td className="px-4 py-2">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${event.cache_hit ? 'bg-green-400' : 'bg-secondary'}`}
                    />
                    <span className="text-xs font-mono text-secondary">
                      {event.cache_hit ? "HIT" : "MISS"}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-2 text-xs font-mono text-secondary">
                  {formatDuration(event.duration_ms)}
                </td>
                <td className="px-4 py-2 text-xs font-mono">
                  {event.error ? (
                    <span className="text-error">{event.error}</span>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </td>
                <td className="px-4 py-2 text-xs font-mono text-secondary">
                  {relativeTime(event.occurred_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </td>
    </tr>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Sessions(): React.ReactElement {
  const [searchParams] = useSearchParams();
  const [agentId, setAgentId] = useState<string>(
    searchParams.get("agent_id") ?? "",
  );
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: agents } = useQuery<Agent[]>({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery<Session[]>({
    queryKey: ["sessions", agentId],
    queryFn: () => fetchSessions(agentId),
  });

  const toggleRow = (id: string): void => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const TABLE_COLS = 4;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-primary text-lg font-semibold">Sessions</h1>

        {/* Agent filter */}
        <div className="flex items-center gap-3">
          <label
            htmlFor="agent-filter"
            className="text-xs text-secondary font-mono"
          >
            Filter:
          </label>
          <select
            id="agent-filter"
            value={agentId}
            onChange={(e) => {
              setAgentId(e.target.value);
              setExpandedId(null);
            }}
            className="bg-elevated border border-white/[0.14] text-primary text-sm px-3 py-1.5 rounded focus:outline-none focus:border-accent focus:ring-0"
          >
            <option value="">All agents</option>
            {agents?.map((agent) => (
              <option key={agent.id} value={agent.id}>
                {agent.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="border-t border-white/[0.07]">
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
            {sessionsLoading ? (
              <tr>
                <td
                  colSpan={TABLE_COLS}
                  className="py-4 px-4 text-sm text-secondary font-mono"
                >
                  Loading sessions…
                </td>
              </tr>
            ) : !sessions || sessions.length === 0 ? (
              <tr>
                <td
                  colSpan={TABLE_COLS}
                  className="py-4 px-4 text-sm text-secondary font-mono"
                >
                  No sessions recorded yet.
                </td>
              </tr>
            ) : (
              sessions.map((session) => (
                <React.Fragment key={session.id}>
                  <tr
                    className="border-b border-white/[0.07] cursor-pointer hover:bg-elevated transition-colors"
                    onClick={() => toggleRow(session.id)}
                  >
                    <td className="py-2 px-4 text-sm font-mono text-accent-light">
                      <span className="flex items-center gap-2">
                        <span className="text-muted text-xs">
                          {expandedId === session.id ? "▾" : "▸"}
                        </span>
                        {session.id.slice(0, 8)}
                      </span>
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

                  {/* Expandable events */}
                  {expandedId === session.id && (
                    <EventsRows sessionId={session.id} colSpan={TABLE_COLS} />
                  )}
                </React.Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Sessions;
