/**
 * Arbiter — Confirm Email Change page.
 *
 * Route: /confirm-email-change?token=<token> (public, no sidebar)
 * Hits GET /auth/confirm-email-change?token=<token> on mount.
 * On success, refreshes user context if authenticated.
 */

import React, { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://localhost:8000/api/v1'

type Status = 'loading' | 'success' | 'error'

function ConfirmEmailChange(): React.ReactElement {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const [status, setStatus] = useState<Status>('loading')
  const [message, setMessage] = useState('')
  const { refreshUser } = useAuth()

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setMessage('Missing confirmation token.')
      return
    }
    fetch(`${API_BASE}/auth/confirm-email-change?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        if (res.ok) {
          setStatus('success')
          // Refresh user context if they're logged in — email changed
          void refreshUser()
        } else {
          const data = await res.json().catch(() => ({}))
          setMessage((data as { detail?: string }).detail ?? 'Confirmation failed.')
          setStatus('error')
        }
      })
      .catch(() => {
        setMessage('Network error. Please try again.')
        setStatus('error')
      })
  }, [token, refreshUser])

  return (
    <div className="min-h-screen bg-base flex items-center justify-center px-4">
      <div className="w-full max-w-sm text-center">
        <div className="inline-flex items-center gap-2 mb-8">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-violet-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">N</span>
          </div>
          <span className="text-primary font-semibold text-lg tracking-tight">Arbiter</span>
        </div>

        <div className="bg-card border border-white/[0.08] rounded-xl p-8 shadow-xl">
          {status === 'loading' && (
            <>
              <div className="w-10 h-10 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-secondary text-sm">Confirming your new email…</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="w-12 h-12 rounded-full bg-success/10 border border-success/20 flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h1 className="text-lg font-bold text-primary mb-2">Email updated!</h1>
              <p className="text-secondary text-sm mb-5">Your email address has been changed and your account is verified.</p>
              <Link
                to="/account"
                className="inline-block bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white font-semibold text-sm py-2.5 px-6 rounded-lg transition-all duration-150"
              >
                Back to Account
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
              <h1 className="text-lg font-bold text-primary mb-2">Confirmation failed</h1>
              <p className="text-secondary text-sm mb-5">{message}</p>
              <Link to="/account" className="text-accent-light hover:text-white text-sm font-medium transition-colors">
                Back to account
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default ConfirmEmailChange
