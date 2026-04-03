/**
 * NexusAI — Login page.
 *
 * Route: /login (public, no sidebar)
 * On success: navigates to / or /onboarding (if onboarding incomplete).
 */

import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authClient } from '../api/client'

interface OnboardingStatus {
  complete: boolean
}

function Login(): React.ReactElement {
  const { login } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await login(email.trim(), password)

      // Check onboarding status
      try {
        const res = await authClient.get<OnboardingStatus>('/onboarding/status')
        if (!res.data.complete) {
          navigate('/onboarding')
          return
        }
      } catch {
        // If endpoint doesn't exist yet, go to dashboard
      }

      navigate('/')
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        setError('Invalid email or password.')
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-base flex items-center justify-center font-mono">
      <div className="w-full max-w-sm px-4">
        {/* Wordmark */}
        <div className="text-center mb-10">
          <span className="font-mono text-2xl text-white tracking-tight">NexusAI</span>
          <p className="text-secondary text-xs mt-2">developer-first MCP gateway</p>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-xs text-secondary mb-1 uppercase tracking-wider">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-elevated border border-white/10 text-white font-mono text-sm px-3 py-2 rounded focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs text-secondary mb-1 uppercase tracking-wider">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full bg-elevated border border-white/10 text-white font-mono text-sm px-3 py-2 rounded focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
            />
          </div>

          {error && (
            <p className="text-red-400 text-xs font-mono">{error}</p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-accent hover:bg-violet-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-mono text-sm py-2 rounded transition-colors mt-2"
          >
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="text-center text-xs text-secondary mt-6">
          Don't have an account?{' '}
          <Link to="/register" className="text-accent-light hover:text-white transition-colors">
            Create one
          </Link>
        </p>
      </div>
    </div>
  )
}

export default Login
