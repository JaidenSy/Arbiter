/**
 * NexusAI — Sessions page.
 *
 * Audit log of all agent sessions and their tool call events.
 *
 * TODO (Coder):
 *   - Fetch sessions from GET /api/v1/sessions (paginated, filterable by agent)
 *   - Render table: Session ID (truncated), Agent, Started At, Ended At, Event Count
 *   - Click on a session row → expand or navigate to detail view showing events
 *   - Events table: Tool Name, MCP Server, Cache Hit, Duration, Error, Timestamp
 *   - Filter bar: agent selector dropdown, date range picker
 *   - Cache hit badge (green) / miss (gray) on each event row
 *   - Error rows highlighted in red with tooltip showing error message
 */

import React from 'react'

// TODO: import { useQuery } from '@tanstack/react-query'
// TODO: import { apiClient } from '../api/client'
// TODO: import type { Session } from '../api/types'

function Sessions(): React.ReactElement {
  // TODO: const [selectedAgentId, setSelectedAgentId] = React.useState<string | null>(null)
  // TODO: const { data: sessions, isLoading } = useQuery({
  //   queryKey: ['sessions', selectedAgentId],
  //   queryFn: () =>
  //     apiClient.get<Session[]>('/sessions', {
  //       params: selectedAgentId ? { agent_id: selectedAgentId } : undefined,
  //     }).then(r => r.data),
  // })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Sessions</h1>
        {/* TODO: filter bar (agent selector + date range) */}
      </div>

      {/* TODO: replace with real sessions table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Session</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Agent</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Started</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ended</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Events</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {/* TODO: sessions?.map(s => <SessionRow key={s.id} session={s} />) */}
            <tr>
              <td className="px-6 py-4 text-sm text-gray-400" colSpan={5}>
                No sessions recorded yet.
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* TODO: <SessionEventDrawer /> — slide-in panel with event detail */}
    </div>
  )
}

export default Sessions
