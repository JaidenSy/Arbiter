/**
 * Arbiter — Accept Invite page.
 *
 * Route: /accept-invite?token=<token> (public, no sidebar)
 * Submits to POST /auth/accept-invite; on success logs the user in.
 */

import React, { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArbiterMark } from '../components/ArbiterLogo'

const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://localhost:8000/api/v1'

const ACCESS_KEY = 'arbiter_access_token'
const REFRESH_KEY = 'arbiter_refresh_token'

function AcceptInvite(): React.ReactElement {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''

  const [displayName, setDisplayName] = useState('')
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
      const res = await fetch(`${API_BASE}/auth/accept-invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          display_name: displayName || undefined,
          password,
        }),
      })
      const data = await res.json().catch(() => ({})) as {
        access_token?: string
        refresh_token?: string
        detail?: string
      }

      if (!res.ok) {
        setError(data.detail ?? 'Failed to accept invite.')
        return
      }

      if (data.access_token && data.refresh_token) {
        localStorage.setItem(ACCESS_KEY, data.access_token)
        localStorage.setItem(REFRESH_KEY, data.refresh_token)
        window.location.href = '/'
      }
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
          <p className="text-secondary text-sm">Invalid invite link.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-base flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-6">
            <ArbiterMark size={32} />
            <span className="text-primary font-semibold text-lg tracking-tight">Arbiter</span>
          </div>
          <h1 className="text-xl font-bold text-primary mb-1">You're invited!</h1>
          <p className="text-secondary text-sm">Create your account to join the team.</p>
        </div>

        <div className="bg-surface/80 backdrop-blur-xl border border-white/[0.08] rounded-2xl p-8 shadow-2xl">
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <label htmlFor="displayName" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
                Your Name <span className="text-muted normal-case font-normal">(optional)</span>
              </label>
              <input
                id="displayName"
                type="text"
                autoComplete="name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Jane Smith"
                className="w-full bg-base border border-white/[0.1] text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 focus:border-accent/60 transition-all duration-150 placeholder:text-muted"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-base border border-white/[0.1] text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 focus:border-accent/60 transition-all duration-150 placeholder:text-muted"
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
                className="w-full bg-base border border-white/[0.1] text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 focus:border-accent/60 transition-all duration-150 placeholder:text-muted"
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
              {isSubmitting ? 'Creating account…' : 'Create account'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

export default AcceptInvite
