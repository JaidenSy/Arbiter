/**
 * Arbiter — Verify Email page.
 *
 * Route: /verify-email?token=<token> (public, no sidebar)
 * Hits GET /auth/verify-email?token=<token> on mount.
 */

import React, { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://localhost:8000/api/v1'

type Status = 'loading' | 'success' | 'error'

function VerifyEmail(): React.ReactElement {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const [status, setStatus] = useState<Status>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setMessage('Missing verification token.')
      return
    }
    fetch(`${API_BASE}/auth/verify-email?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        if (res.ok) {
          setStatus('success')
        } else {
          const data = await res.json().catch(() => ({}))
          setMessage((data as { detail?: string }).detail ?? 'Verification failed.')
          setStatus('error')
        }
      })
      .catch(() => {
        setMessage('Network error. Please try again.')
        setStatus('error')
      })
  }, [token])

  return (
    <div className="min-h-screen bg-base flex items-center justify-center px-4">
      <div className="w-full max-w-sm text-center">
        <div className="inline-flex items-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
            <span className="text-white font-bold text-sm">N</span>
          </div>
          <span className="text-primary font-semibold text-lg tracking-tight">Arbiter</span>
        </div>

        <div className="bg-card border border-border rounded-xl p-8 shadow-xl">
          {status === 'loading' && (
            <>
              <div className="w-10 h-10 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-secondary text-sm">Verifying your email…</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="w-12 h-12 rounded-full bg-success/10 border border-success/20 flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h1 className="text-lg font-bold text-primary mb-2">Email verified!</h1>
              <p className="text-secondary text-sm mb-5">Your account is now fully active.</p>
              <Link
                to="/dashboard"
                className="inline-block bg-accent hover:bg-accent-light text-white font-semibold text-sm py-2.5 px-6 rounded-lg transition-all duration-150"
              >
                Go to Dashboard
              </Link>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="w-12 h-12 rounded-full bg-error/10 border border-error/20 flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h1 className="text-lg font-bold text-primary mb-2">Verification failed</h1>
              <p className="text-secondary text-sm mb-5">{message}</p>
              <Link to="/login" className="text-accent-light hover:text-white text-sm font-medium transition-colors">
                Back to sign in
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default VerifyEmail
