/**
 * Arbiter Frontend — Root application component.
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

import React, { Suspense, lazy } from 'react'
import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import ProtectedRoute from './components/ProtectedRoute'
import { useAuth } from './context/AuthContext'

// ── Lazy page imports — each page becomes its own chunk ───────────────────────

const Dashboard    = lazy(() => import('./pages/Dashboard'))
const Agents       = lazy(() => import('./pages/Agents'))
const MCPServers   = lazy(() => import('./pages/MCPServers'))
const Sessions     = lazy(() => import('./pages/Sessions'))
const SessionTrace = lazy(() => import('./pages/SessionTrace'))
const Settings     = lazy(() => import('./pages/Settings'))
const Permissions  = lazy(() => import('./pages/Permissions'))
const Vault        = lazy(() => import('./pages/Vault'))
const Login        = lazy(() => import('./pages/Login'))
const Register     = lazy(() => import('./pages/Register'))
const Onboarding   = lazy(() => import('./pages/Onboarding'))
const AuthCallback = lazy(() => import('./pages/AuthCallback'))
const Landing        = lazy(() => import('./pages/Landing'))
const Docs           = lazy(() => import('./pages/Docs'))
const Account        = lazy(() => import('./pages/Account'))
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'))
const ResetPassword  = lazy(() => import('./pages/ResetPassword'))
const VerifyEmail    = lazy(() => import('./pages/VerifyEmail'))
const AcceptInvite   = lazy(() => import('./pages/AcceptInvite'))
const Members        = lazy(() => import('./pages/Members'))

// ── Shared loading fallback ───────────────────────────────────────────────────

function PageLoader(): React.ReactElement {
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

  if (isLoading) return <PageLoader />

  if (!user && !isLoading) {
    return <Landing />
  }

  return (
    <AppLayout>
      <Dashboard />
    </AppLayout>
  )
}

function App(): React.ReactElement {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* ── Public routes (no sidebar) ──────────────────────────────────── */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/docs" element={<Docs />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/accept-invite" element={<AcceptInvite />} />

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
        <Route
          path="/account"
          element={
            <ProtectedRoute>
              <AppLayout><Account /></AppLayout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/organization"
          element={
            <ProtectedRoute>
              <AppLayout><Members /></AppLayout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </Suspense>
  )
}

export default App
