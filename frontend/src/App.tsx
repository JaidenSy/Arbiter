/**
 * Nexvault Frontend — Root application component.
 *
 * Routes:
 *   /            → Dashboard    (stats, cache hit rate, recent sessions)
 *   /agents      → Agents       (list, register, deactivate)
 *   /mcp-servers → MCPServers   (list, add, edit, deactivate)
 *   /sessions    → Sessions     (audit log, event drill-down)
 *   /settings    → Settings     (API key, gateway URL, about)
 *   /permissions → Permissions  (per-agent tool permission grant/revoke)
 *   /vault       → Vault        (per-agent secret management, AES-256-GCM encrypted)
 *
 * Auth routes (no sidebar, no ProtectedRoute):
 *   /login       → Login page
 *   /register    → Register page
 *
 * Protected wizard (no sidebar):
 *   /onboarding  → Onboarding wizard (new users only)
 */

import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import ProtectedRoute from './components/ProtectedRoute'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import MCPServers from './pages/MCPServers'
import Sessions from './pages/Sessions'
import SessionTrace from './pages/SessionTrace'
import Settings from './pages/Settings'
import Permissions from './pages/Permissions'
import Vault from './pages/Vault'
import Login from './pages/Login'
import Register from './pages/Register'
import Onboarding from './pages/Onboarding'
import AuthCallback from './pages/AuthCallback'
import { useAuth } from './context/AuthContext'

// ── Layout wrapper for sidebar pages ─────────────────────────────────────────

function AppLayout({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <div className="flex min-h-screen bg-base">
      <Sidebar />
      <main className="flex-1 ml-[52px] min-h-screen">
        {children}
      </main>
    </div>
  )
}

// ── Root redirect — send unauthenticated users to /login ──────────────────────

function RootRedirect(): React.ReactElement {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center gap-2">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-2 h-2 rounded-full bg-accent animate-pulse"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    )
  }

  if (!user) {
    const apiKey = localStorage.getItem('nexvault_api_key')
    if (!apiKey) return <Navigate to="/login" replace />
  }

  return (
    <AppLayout>
      <Dashboard />
    </AppLayout>
  )
}

function App(): React.ReactElement {
  return (
    <Routes>
      {/* ── Public auth routes (no sidebar) ─────────────────────────────── */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* ── Protected onboarding (no sidebar) ───────────────────────────── */}
      <Route
        path="/onboarding"
        element={
          <ProtectedRoute>
            <Onboarding />
          </ProtectedRoute>
        }
      />

      {/* ── Root — smart redirect ────────────────────────────────────────── */}
      <Route path="/" element={<RootRedirect />} />

      {/* ── Protected app routes (with sidebar) ─────────────────────────── */}
      <Route
        path="/agents"
        element={
          <ProtectedRoute>
            <AppLayout><Agents /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/mcp-servers"
        element={
          <ProtectedRoute>
            <AppLayout><MCPServers /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/sessions"
        element={
          <ProtectedRoute>
            <AppLayout><Sessions /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/sessions/:id"
        element={
          <ProtectedRoute>
            <AppLayout><SessionTrace /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <AppLayout><Settings /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/permissions"
        element={
          <ProtectedRoute>
            <AppLayout><Permissions /></AppLayout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/vault"
        element={
          <ProtectedRoute>
            <AppLayout><Vault /></AppLayout>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

export default App
