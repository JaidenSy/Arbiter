/**
 * Arbiter — Forgot Password page.
 *
 * Route: /forgot-password (public, no sidebar)
 * Submits email to POST /auth/forgot-password; always shows success to avoid email enumeration.
 */

import React, { useState } from 'react'
import { Link } from 'react-router-dom'

const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://localhost:8000/api/v1'

function ForgotPassword(): React.ReactElement {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setIsSubmitting(true)
    try {
      await fetch(`${API_BASE}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
    } finally {
      setSubmitted(true)
      setIsSubmitting(false)
    }
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
          <h1 className="text-xl font-bold text-primary mb-1">Reset your password</h1>
          <p className="text-secondary text-sm">
            {submitted
              ? "Check your inbox for a reset link."
              : "Enter your email and we'll send you a reset link."}
          </p>
        </div>

        <div className="bg-card border border-white/[0.08] rounded-xl p-6 shadow-xl">
          {submitted ? (
            <div className="text-center py-4">
              <div className="w-12 h-12 rounded-full bg-success/10 border border-success/20 flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <p className="text-secondary text-sm">
                If <span className="text-primary font-medium">{email}</span> has an account, a reset link is on its way.
              </p>
              <Link to="/login" className="mt-4 inline-block text-accent-light hover:text-white text-sm font-medium transition-colors">
                Back to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div>
                <label htmlFor="email" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full bg-base border border-white/[0.1] text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 focus:border-accent/60 transition-all duration-150 placeholder:text-muted"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-all duration-150 hover:shadow-[0_0_20px_rgba(217,119,6,0.35)] mt-1"
              >
                {isSubmitting ? 'Sending…' : 'Send reset link'}
              </button>

              <p className="text-center text-xs text-secondary mt-1">
                <Link to="/login" className="text-accent-light hover:text-white font-medium transition-colors">
                  Back to sign in
                </Link>
              </p>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

export default ForgotPassword
