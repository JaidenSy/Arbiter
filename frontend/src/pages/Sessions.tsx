/**
 * NexusAI — Sessions page.
 *
 * Audit log of all agent sessions.
 *   - Agent filter dropdown
 *   - Sessions table — rows navigate to /sessions/:id for the full trace view
 */

import React, { useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { authClient } from "../api/client";
import type { Agent, Session } from "../api/types";

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchAgents = (): Promise<Agent[]> =>
  authClient.get<Agent[]>("/agents").then((r) => r.data);

const fetchSessions = (agentId: string): Promise<Session[]> =>
  authClient
    .get<Session[]>("/sessions", {
      params: agentId ? { agent_id: agentId } : undefined,
    })
    .then((r) => r.data);

// ── Helpers ───────────────────────────────────────────────────────────────────

function agentDisplayName(agentId: string, agents: Agent[] | undefined): string {
  const match = agents?.find((a) => a.id === agentId)
  return match ? match.name : agentId.slice(0, 8)
}

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
  const [agentId, setAgentId] = useState<string>(
    searchParams.get("agent_id") ?? "",
  );

  const { data: agents } = useQuery<Agent[]>({
    queryKey: ["agents"],
    queryFn: fetchAgents,
  });

  const { data: sessions, isLoading: sessionsLoading } = useQuery<Session[]>({
    queryKey: ["sessions", agentId],
    queryFn: () => fetchSessions(agentId),
  });

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
            onChange={(e) => setAgentId(e.target.value)}
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
                <td colSpan={TABLE_COLS} className="py-16 px-4 text-center">
                  <svg className="mx-auto mb-3 text-muted" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                    <polyline points="10 9 9 9 8 9"/>
                  </svg>
                  <p className="text-secondary text-sm font-mono mb-1">No sessions recorded yet.</p>
                  <p className="text-muted text-xs">Sessions appear here once an agent makes its first tool call.</p>
                </td>
              </tr>
            ) : (
              sessions.map((session) => (
                <tr
                  key={session.id}
                  className="border-b border-white/[0.07] cursor-pointer hover:bg-elevated transition-colors"
                  onClick={() => navigate(`/sessions/${session.id}`)}
                >
                  <td className="py-2 px-4 text-sm font-mono text-accent-light">
                    {session.id.slice(0, 8)}
                  </td>
                  <td className="py-2 px-4 text-sm font-mono text-secondary">
                    {agentDisplayName(session.agent_id, agents)}
                  </td>
                  <td className="py-2 px-4 text-sm text-secondary">
                    {relativeTime(session.started_at)}
                  </td>
                  <td className="py-2 px-4 text-sm font-mono text-secondary">
                    {session.event_count ?? session.events?.length ?? 0}
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
