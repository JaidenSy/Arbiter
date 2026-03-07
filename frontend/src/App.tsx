/**
 * NexusAI Frontend — Root application component.
 *
 * Defines the top-level routing structure.  All page-level components live
 * in src/pages/.  The nav bar and shared layout are TODO for the Coder.
 *
 * Routes:
 *   /            → Dashboard   (stats, cache hit rate, recent sessions)
 *   /agents      → Agents      (list, register, deactivate)
 *   /sessions    → Sessions    (audit log, event drill-down)
 */

import React from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import Sessions from './pages/Sessions'

// TODO: extract NavBar into src/components/NavBar.tsx

function App(): React.ReactElement {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation — TODO: style with Tailwind, make responsive */}
      <nav className="bg-white border-b border-gray-200 px-6 py-4 flex gap-6">
        <span className="font-bold text-lg text-indigo-600">NexusAI</span>
        <NavLink to="/" end className="text-gray-600 hover:text-indigo-600">
          Dashboard
        </NavLink>
        <NavLink to="/agents" className="text-gray-600 hover:text-indigo-600">
          Agents
        </NavLink>
        <NavLink to="/sessions" className="text-gray-600 hover:text-indigo-600">
          Sessions
        </NavLink>
      </nav>

      {/* Page content */}
      <main className="p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/sessions" element={<Sessions />} />
          {/* TODO: <Route path="/sessions/:id" element={<SessionDetail />} /> */}
        </Routes>
      </main>
    </div>
  )
}

export default App
