/**
 * Arbiter: ToS/Privacy consent page for SSO sign-ups.
 *
 * Route: /consent (public, requires valid JWT in localStorage)
 *
 * Shown when a user signs up via Google or GitHub for the first time.
 * Calls POST /auth/sso/accept-tos, then navigates to the app.
 */

import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authClient } from '../api/client'

function Consent(): React.ReactElement {
  const navigate = useNavigate()
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAccept = async (): Promise<void> => {
    setIsSubmitting(true)
    setError(null)
    try {
      await authClient.post('/auth/sso/accept-tos')
      void navigate('/', { replace: true })
    } catch {
      setError('Something went wrong. Please try again.')
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-base flex items-center justify-center relative overflow-hidden">
      {/* Background glows */}
      <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-accent/10 blur-[120px] pointer-events-none" />
      <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-teal/8 blur-[120px] pointer-events-none" />

      {/* Dot grid texture */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.035]"
        style={{
          backgroundImage: 'radial-gradient(circle, #2563EB 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      />

      <div className="relative w-full max-w-sm px-4 animate-fade-in">
        <div className="bg-surface/85 backdrop-blur-xl border border-border-strong rounded-2xl p-8 shadow-2xl">
          <div className="text-center mb-6">
            <span className="font-display text-primary font-semibold text-2xl tracking-tight">One last step</span>
            <p className="text-secondary text-sm mt-2">Review and accept our terms to continue</p>
          </div>

          <div className="space-y-3 mb-6">
            <div className="flex items-start gap-3 p-3.5 rounded-lg bg-base border border-border">
              <div className="w-8 h-8 rounded-md bg-accent/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path d="M13.5 2H6a1 1 0 0 0-1 1v1H3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1h1.5A1.5 1.5 0 0 0 15 12.5v-9A1.5 1.5 0 0 0 13.5 2zM10 13H3V5h2v7.5A1.5 1.5 0 0 0 6.5 14H10v-1zm3.5-1H6V3h7.5a.5.5 0 0 1 .5.5v8a.5.5 0 0 1-.5.5z" fill="currentColor" className="text-accent"/>
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-primary">Terms of Service</p>
                <p className="text-xs text-secondary mt-0.5">
                  Covers your rights and responsibilities when using Arbiter.{' '}
                  <Link to="/terms" target="_blank" rel="noopener noreferrer" className="text-accent-light hover:text-primary underline underline-offset-2 transition-colors">
                    Read terms
                  </Link>
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 rounded-lg bg-base border border-border">
              <div className="w-8 h-8 rounded-md bg-accent/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 13A6 6 0 1 1 8 2a6 6 0 0 1 0 12zm-.5-5V5h1v4h-1zm0 2h1v1h-1v-1z" fill="currentColor" className="text-accent"/>
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-primary">Privacy Policy</p>
                <p className="text-xs text-secondary mt-0.5">
                  Explains what data we collect and how we use it.{' '}
                  <Link to="/privacy" target="_blank" rel="noopener noreferrer" className="text-accent-light hover:text-primary underline underline-offset-2 transition-colors">
                    Read policy
                  </Link>
                </p>
              </div>
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2 mb-4">
              <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
              <p className="text-error text-xs">{error}</p>
            </div>
          )}

          <button
            type="button"
            onClick={() => void handleAccept()}
            disabled={isSubmitting}
            className="press w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover-glow-standard"
          >
            {isSubmitting ? 'Saving…' : 'Agree and continue to Arbiter'}
          </button>

          <p className="text-center text-[11px] text-muted mt-4 leading-relaxed">
            By continuing you agree to the terms above. Last updated May 2026.
          </p>
        </div>
      </div>
    </div>
  )
}

export default Consent
