/**
 * Arbiter: Reset Password page.
 *
 * Route: /reset-password?token=<token> (public, no sidebar)
 * Submits new password to POST /auth/reset-password.
 */

import React, { useState } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import PasswordRequirements from '../components/PasswordRequirements'
import { isPasswordValid } from '../utils/password'

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

    if (!isPasswordValid(password)) {
      setError('Password does not meet all the requirements listed below.')
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
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
              <span className="text-white font-bold text-sm">N</span>
            </div>
            <span className="text-primary font-semibold text-lg tracking-tight">Arbiter</span>
          </div>
          <h1 className="text-xl font-bold text-primary mb-1">Choose a new password</h1>
          <p className="text-secondary text-sm">Choose a strong password you haven't used before.</p>
        </div>

        <div className="bg-card border border-border rounded-xl p-6 shadow-xl">
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
                className="w-full bg-base border border-border text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 focus:border-accent/60 transition-all duration-150 placeholder:text-muted"
              />
              {password.length > 0 && (
                <div className="mt-2">
                  <PasswordRequirements password={password} />
                </div>
              )}
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
                className="w-full bg-base border border-border text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 focus:border-accent/60 transition-all duration-150 placeholder:text-muted"
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
              className="w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-all duration-150 hover-glow-standard mt-1"
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
