/**
 * Arbiter — Reset Password page.
 *
 * Route: /reset-password?token=<token> (public, no sidebar)
 * Submits new password to POST /auth/reset-password.
 */

import React, { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'

const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://localhost:8000/api/v1'

function ResetPassword(): React.ReactElement {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      const res = await fetch(`${API_BASE}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError((data as { detail?: string }).detail ?? 'Reset failed. The link may have expired.')
        return
      }
      navigate('/login?reset=1')
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-secondary">Invalid reset link.</p>
          <Link to="/forgot-password" className="text-accent-light hover:text-white text-sm mt-2 inline-block">
            Request a new one
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-base flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-6">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-violet-600 flex items-center justify-center">
              <span className="text-white font-bold text-sm">N</span>
            </div>
            <span className="text-primary font-semibold text-lg tracking-tight">Arbiter</span>
          </div>
          <h1 className="text-xl font-bold text-primary mb-1">Choose a new password</h1>
          <p className="text-secondary text-sm">Must be at least 8 characters.</p>
        </div>

        <div className="bg-card border border-white/[0.08] rounded-xl p-6 shadow-xl">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label htmlFor="password" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
                New Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-elevated/80 border border-white/[0.1] text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 focus:border-accent/60 transition-all duration-150 placeholder:text-muted"
              />
            </div>

            <div>
              <label htmlFor="confirm" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
                Confirm Password
              </label>
              <input
                id="confirm"
                type="password"
                required
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-elevated/80 border border-white/[0.1] text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 focus:border-accent/60 transition-all duration-150 placeholder:text-muted"
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
                <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
                <p className="text-error text-xs">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-all duration-150 hover:shadow-[0_0_20px_rgba(124,58,237,0.35)] mt-1"
            >
              {isSubmitting ? 'Saving…' : 'Set new password'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default ResetPassword
