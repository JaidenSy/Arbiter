/**
 * Arbiter — ProtectedRoute component.
 *
 * Wraps routes that require authentication.
 * - Loading: shows centered amber pulse spinner
 * - Unauthenticated: redirects to /login
 * - Authenticated: renders children
 */

import React from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

function Spinner(): React.ReactElement {
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

interface ProtectedRouteProps {
  children: React.ReactNode
}

function ProtectedRoute({ children }: ProtectedRouteProps): React.ReactElement {
  const { user, isLoading } = useAuth()

  if (isLoading) return <Spinner />
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default ProtectedRoute
