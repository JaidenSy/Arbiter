/**
 * NexusAI — Agents page.
 *
 * Lists registered agents and allows registering new ones.
 *
 * TODO (Coder):
 *   - Fetch agents list from GET /api/v1/agents
 *   - Render table with columns: Name, Description, Active, Created At, Actions
 *   - "Register Agent" button opens a modal/drawer with AgentCreate form
 *   - On successful POST /api/v1/agents, show one-time API key in a modal
 *     (copyable, with warning that it will not be shown again)
 *   - "Deactivate" button calls DELETE /api/v1/agents/{id} with confirmation
 *   - Optimistic UI updates via TanStack Query mutation + invalidation
 */

import React from 'react'

// TODO: import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
// TODO: import { apiClient } from '../api/client'
// TODO: import type { Agent, AgentCreateResponse } from '../api/types'

function Agents(): React.ReactElement {
  // TODO: const { data: agents, isLoading, error } = useQuery({
  //   queryKey: ['agents'],
  //   queryFn: () => apiClient.get<Agent[]>('/agents').then(r => r.data),
  // })

  // TODO: const registerMutation = useMutation({ ... })
  // TODO: const deactivateMutation = useMutation({ ... })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Agents</h1>
        <button
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700"
          onClick={() => {
            // TODO: open registration modal
          }}
        >
          Register Agent
        </button>
      </div>

      {/* TODO: replace with real data table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {/* TODO: agents?.map(agent => <AgentRow key={agent.id} agent={agent} />) */}
            <tr>
              <td className="px-6 py-4 text-sm text-gray-400" colSpan={5}>
                No agents registered yet.
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* TODO: <RegisterAgentModal /> */}
      {/* TODO: <ApiKeyRevealModal /> — shows one-time key after registration */}
    </div>
  )
}

export default Agents
