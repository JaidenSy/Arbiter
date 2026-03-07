/**
 * NexusAI — Dashboard page.
 *
 * The landing page of the admin dashboard.  Displays a high-level overview
 * of gateway activity.
 *
 * TODO (Coder):
 *   - Fetch stats from GET /api/v1/stats (endpoint to be added to backend)
 *   - Render cache hit rate chart using Recharts LineChart or AreaChart
 *   - Show "Recent Sessions" table (last 10 sessions, linked to /sessions/:id)
 *   - Show active agent count and active MCP server count as stat cards
 *   - Show total tool calls today vs yesterday (delta trend indicator)
 */

import React from 'react'

// TODO: import { useQuery } from '@tanstack/react-query'
// TODO: import { apiClient } from '../api/client'
// TODO: import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

function Dashboard(): React.ReactElement {
  // TODO: const { data: stats, isLoading } = useQuery({
  //   queryKey: ['dashboard-stats'],
  //   queryFn: () => apiClient.get('/stats').then(r => r.data),
  // })

  return (
    <div>
      <h1 className="text-2xl font-semibold text-gray-900 mb-6">Dashboard</h1>

      {/* TODO: stat cards row */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Active Agents</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">—</p>
          {/* TODO: fill with real data */}
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">MCP Servers</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">—</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Tool Calls Today</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">—</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <p className="text-sm text-gray-500">Cache Hit Rate</p>
          <p className="text-3xl font-bold text-indigo-600 mt-1">—%</p>
        </div>
      </div>

      {/* TODO: cache hit rate chart */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Cache Hit Rate (7 days)</h2>
        <div className="h-48 flex items-center justify-center text-gray-400">
          {/* TODO: <ResponsiveContainer> + <AreaChart> with real data */}
          Chart placeholder
        </div>
      </div>

      {/* TODO: recent sessions table */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Recent Sessions</h2>
        <p className="text-gray-400 text-sm">TODO: render sessions table</p>
      </div>
    </div>
  )
}

export default Dashboard
