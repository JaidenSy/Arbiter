/**
 * Arbiter — Register page.
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

  const inputClass = "w-full bg-base border border-border-strong text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-[border-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] placeholder:text-muted"
  const labelClass = "block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest"

  return (
    <div className="min-h-screen bg-base flex items-center justify-center relative overflow-hidden py-10">
      {/* Background glows */}
      <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-accent/10 blur-[120px] pointer-events-none" />
      <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-teal/8 blur-[120px] pointer-events-none" />

      {/* Dot grid texture */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.035]"
        style={{
          backgroundImage: 'radial-gradient(circle, #F59E0B 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      />

      <div className="relative w-full max-w-sm px-4 animate-fade-in">
        {/* Card */}
        <div className="bg-surface/85 backdrop-blur-xl border border-border-strong rounded-2xl p-8 shadow-2xl">
          {/* Wordmark */}
          <div className="text-center mb-8">
            <span className="font-display text-primary font-semibold text-3xl tracking-tight">Arbiter</span>
            <p className="text-secondary text-sm mt-2">Create your organization</p>
          </div>

          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            <div>
              <label htmlFor="org-name" className={labelClass}>
                Organization Name
              </label>
              <input
                id="org-name"
                type="text"
                required
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Acme Corp"
                className={inputClass}
              />
            </div>

            <div>
              <label htmlFor="email" className={labelClass}>
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
                className={inputClass}
              />
            </div>

            <div>
              <label htmlFor="password" className={labelClass}>
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
                className={inputClass}
              />
            </div>

            <div>
              <label htmlFor="confirm-password" className={labelClass}>
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
                className={inputClass}
              />
            </div>

            {inviteRequired && (
              <div>
                <label htmlFor="invite-code" className={labelClass}>
                  Invite Code
                </label>
                <input
                  id="invite-code"
                  type="text"
                  required
                  value={inviteCode}
                  onChange={(e) => setInviteCode(e.target.value)}
                  placeholder="Enter your invite code"
                  className={inputClass}
                />
              </div>
            )}

            {error && (
              <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
                <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
                <p className="text-error text-xs">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="press w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover-glow-standard mt-2"
            >
              {isSubmitting ? 'Creating account…' : 'Create account'}
            </button>
          </form>

          <p className="text-center text-xs text-secondary mt-5">
            Already have an account?{' '}
            <Link to="/login" className="text-accent-light hover:text-white font-medium transition-colors">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

export default Register
