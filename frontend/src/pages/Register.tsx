/**
 * NexusAI — Register page.
 *
 * Route: /register (public, no sidebar)
 * On success: auto-logged in (tokens from backend), navigates to /onboarding.
 */

import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

function Register(): React.ReactElement {
  const { register } = useAuth()
  const navigate = useNavigate()

  const inviteRequired = import.meta.env.VITE_INVITE_REQUIRED === 'true'

  const [orgName, setOrgName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const validate = (): string | null => {
    if (!orgName.trim()) return 'Organization name is required.'
    if (!email.trim()) return 'Email is required.'
    if (password.length < 8) return 'Password must be at least 8 characters.'
    if (password !== confirmPassword) return 'Passwords do not match.'
    if (inviteRequired && !inviteCode.trim()) return 'An invite code is required.'
    return null
  }

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }
    setError(null)
    setIsSubmitting(true)

    try {
      await register(orgName.trim(), email.trim(), password, inviteCode.trim())
      navigate('/onboarding')
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number; data?: { detail?: string } } })?.response
      if (status?.status === 409) {
        setError('An account with that email already exists.')
      } else if (status?.data?.detail) {
        setError(status.data.detail)
      } else {
        setError('Registration failed. Please try again.')
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
          <p className="text-secondary text-xs mt-2">create your organization</p>
        </div>

        <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
          <div>
            <label htmlFor="org-name" className="block text-xs text-secondary mb-1 uppercase tracking-wider">
              Organization Name
            </label>
            <input
              id="org-name"
              type="text"
              required
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="Acme Corp"
              className="w-full bg-elevated border border-white/10 text-white font-mono text-sm px-3 py-2 rounded focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
            />
          </div>

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
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="min 8 characters"
              className="w-full bg-elevated border border-white/10 text-white font-mono text-sm px-3 py-2 rounded focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
            />
          </div>

          <div>
            <label htmlFor="confirm-password" className="block text-xs text-secondary mb-1 uppercase tracking-wider">
              Confirm Password
            </label>
            <input
              id="confirm-password"
              type="password"
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="repeat password"
              className="w-full bg-elevated border border-white/10 text-white font-mono text-sm px-3 py-2 rounded focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
            />
          </div>

          {inviteRequired && (
            <div>
              <label htmlFor="invite-code" className="block text-xs text-secondary mb-1 uppercase tracking-wider">
                Invite Code
              </label>
              <input
                id="invite-code"
                type="text"
                required
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                placeholder="Enter your invite code"
                className="w-full bg-elevated border border-white/10 text-white font-mono text-sm px-3 py-2 rounded focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
              />
            </div>
          )}

          {error && (
            <p className="text-red-400 text-xs font-mono">{error}</p>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-accent hover:bg-violet-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-mono text-sm py-2 rounded transition-colors mt-2"
          >
            {isSubmitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="text-center text-xs text-secondary mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-accent-light hover:text-white transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}

export default Register
