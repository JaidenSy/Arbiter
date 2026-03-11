/**
 * NexusAI — Sessions page.
 *
 * Audit log of all agent sessions and their tool call events.
 *   - Agent filter dropdown
 *   - Sessions table with expandable inline event rows
 *   - Events lazy-loaded per session on row expand
 */

import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import type { Agent, Session, SessionEvent } from '../api/types'
import Badge from '../components/Badge'

// ── Data fetchers ─────────────────────────────────────────────────────────────

const fetchAgents = (): Promise<Agent[]> =>
  apiClient.get<Agent[]>('/agents').then((r) => r.data)

const fetchSessions = (agentId: string): Promise<Session[]> =>
  apiClient
    .get<Session[]>('/sessions', {
      params: agentId ? { agent_id: agentId } : undefined,
    })
    .then((r) => r.data)

const fetchSessionEvents = (sessionId: string): Promise<SessionEvent[]> =>
  apiClient.get<SessionEvent[]>(`/sessions/${sessionId}/events`).then((r) => r.data)

// ── Helpers ───────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  return `${ms} ms`
}

// ── Events sub-table ──────────────────────────────────────────────────────────

interface EventsRowsProps {
  sessionId: string
  colSpan: number
}

function EventsRows({ sessionId, colSpan }: EventsRowsProps): React.ReactElement {
  const { data: events, isLoading } = useQuery<SessionEvent[]>({
    queryKey: ['events', sessionId],
    queryFn: () => fetchSessionEvents(sessionId),
  })

  if (isLoading) {
    return (
      <tr>
        <td colSpan={colSpan} className="px-10 py-4 text-sm text-gray-400">
          Loading events…
        </td>
      </tr>
    )
  }

  if (!events || events.length === 0) {
    return (
      <tr>
        <td colSpan={colSpan} className="px-10 py-4 text-sm text-gray-400">
          No events recorded for this session.
        </td>
      </tr>
    )
  }

  return (
    <>
      {/* Sub-header */}
      <tr className="bg-indigo-50">
        <td colSpan={colSpan} className="px-0 py-0">
          <table className="min-w-full">
            <thead>
              <tr>
                <th className="pl-10 pr-4 py-2 text-left text-xs font-medium text-indigo-700 uppercase w-1/4">
                  Tool
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-indigo-700 uppercase">
                  Cache
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-indigo-700 uppercase">
                  Duration
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-indigo-700 uppercase">
                  Error
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-indigo-700 uppercase">
                  Time
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-indigo-100">
              {events.map((event) => (
                <tr key={event.id} className="bg-indigo-50 hover:bg-indigo-100 transition-colors">
                  <td className="pl-10 pr-4 py-2 text-xs font-mono text-gray-900">
                    {event.tool_name}
                  </td>
                  <td className="px-4 py-2">
                    <Badge variant={event.cache_hit ? 'success' : 'neutral'}>
                      {event.cache_hit ? 'HIT' : 'MISS'}
                    </Badge>
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-600">
                    {formatDuration(event.duration_ms)}
                  </td>
                  <td className="px-4 py-2 text-xs">
                    {event.error ? (
                      <span className="text-red-600">{event.error}</span>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-600">
                    {relativeTime(event.occurred_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </td>
      </tr>
    </>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Sessions(): React.ReactElement {
  const [agentId, setAgentId] = useState<string>('')
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const { data: agents } = useQuery<Agent[]>({
    queryKey: ['agents'],
    queryFn: fetchAgents,
  })

  const { data: sessions, isLoading: sessionsLoading } = useQuery<Session[]>({
    queryKey: ['sessions', agentId],
    queryFn: () => fetchSessions(agentId),
  })

  const toggleRow = (id: string): void => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  const TABLE_COLS = 4

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Sessions</h1>

        {/* Agent filter */}
        <div className="flex items-center gap-3">
          <label htmlFor="agent-filter" className="text-sm text-gray-600 font-medium">
            Filter by agent:
          </label>
          <select
            id="agent-filter"
            value={agentId}
            onChange={(e) => {
              setAgentId(e.target.value)
              setExpandedId(null)
            }}
            className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
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

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Session</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Agent</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Started</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Events</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {sessionsLoading ? (
              <tr>
                <td colSpan={TABLE_COLS} className="px-6 py-4 text-sm text-gray-400">
                  Loading sessions…
                </td>
              </tr>
            ) : !sessions || sessions.length === 0 ? (
              <tr>
                <td colSpan={TABLE_COLS} className="px-6 py-4 text-sm text-gray-400">
                  No sessions recorded yet.
                </td>
              </tr>
            ) : (
              sessions.map((session) => (
                <React.Fragment key={session.id}>
                  <tr
                    className="cursor-pointer hover:bg-gray-50 transition-colors"
                    onClick={() => toggleRow(session.id)}
                  >
                    <td className="px-6 py-4 text-sm font-mono text-gray-900">
                      <span className="flex items-center gap-2">
                        <span className="text-gray-400 text-xs">
                          {expandedId === session.id ? '▾' : '▸'}
                        </span>
                        {session.id.slice(0, 8)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm font-mono text-gray-600">
                      {session.agent_id.slice(0, 8)}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {relativeTime(session.started_at)}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {session.events?.length ?? '—'}
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
  )
}

export default Sessions
