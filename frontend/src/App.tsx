/**
 * NexusAI Frontend — Root application component.
 *
 * Routes:
 *   /            → Dashboard    (stats, cache hit rate, recent sessions)
 *   /agents      → Agents       (list, register, deactivate)
 *   /mcp-servers → MCPServers   (list, add, edit, deactivate)
 *   /sessions    → Sessions     (audit log, event drill-down)
 *   /settings    → Settings     (API key, gateway URL, about)
 *   /permissions → Permissions  (per-agent tool permission grant/revoke)
 *   /vault       → Vault        (per-agent secret management, AES-256-GCM encrypted)
 */

import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import MCPServers from './pages/MCPServers'
import Sessions from './pages/Sessions'
import SessionTrace from './pages/SessionTrace'
import Settings from './pages/Settings'
import Permissions from './pages/Permissions'
import Vault from './pages/Vault'

function App(): React.ReactElement {
  return (
    <div className="flex min-h-screen bg-base">
      <Sidebar />
      <main className="flex-1 ml-[52px] min-h-screen">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/mcp-servers" element={<MCPServers />} />
          <Route path="/sessions" element={<Sessions />} />
          <Route path="/sessions/:id" element={<SessionTrace />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/permissions" element={<Permissions />} />
          <Route path="/vault" element={<Vault />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
