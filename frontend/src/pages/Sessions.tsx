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
                <td
                  colSpan={TABLE_COLS}
                  className="py-4 px-4 text-sm text-secondary font-mono"
                >
                  No sessions recorded yet.
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
                    {session.agent_id.slice(0, 8)}
                  </td>
                  <td className="py-2 px-4 text-sm text-secondary">
                    {relativeTime(session.started_at)}
                  </td>
                  <td className="py-2 px-4 text-sm font-mono text-secondary">
                    {session.events?.length ?? "—"}
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
