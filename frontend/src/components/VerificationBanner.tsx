/**
 * Arbiter — VerificationBanner component.
 *
 * Renders a sticky amber warning banner when the authenticated user has not
 * verified their email address.  The banner:
 *   - Reads `user.is_verified` from AuthContext.
 *   - Calls POST /auth/send-verification to resend the email.
 *   - Can be dismissed for the session via localStorage key `dismissedVerifyBanner`.
 *   - Disappears immediately once `refreshUser()` detects `is_verified = true`.
 */

import React, { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { authClient } from '../api/client'

const DISMISS_KEY = 'dismissedVerifyBanner'

function VerificationBanner(): React.ReactElement | null {
  const { user, refreshUser } = useAuth()
  const [dismissed, setDismissed] = useState<boolean>(
    () => localStorage.getItem(DISMISS_KEY) === '1'
  )
  const [resendState, setResendState] = useState<'idle' | 'loading' | 'sent' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState<string>('')

  // Only show when authenticated and unverified and not dismissed
  if (!user || user.is_verified || dismissed) return null

  function handleDismiss(): void {
    localStorage.setItem(DISMISS_KEY, '1')
    setDismissed(true)
  }

  async function handleResend(): Promise<void> {
    if (resendState === 'loading' || resendState === 'sent') return
    setResendState('loading')
    setErrorMsg('')
    try {
      await authClient.post('/auth/send-verification')
      setResendState('sent')
      // Refresh in case the user verified in another tab between now and resend
      await refreshUser()
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setErrorMsg(detail ?? 'Failed to send. Try again.')
      setResendState('error')
    }
  }

  return (
    <div
      role="alert"
      aria-live="polite"
      className="sticky top-0 z-50 flex items-center gap-3 px-4 py-2.5 bg-warning/10 border-b border-warning/30 text-warning-text text-sm"
    >
      {/* Warning icon */}
      <svg
        className="w-4 h-4 text-warning flex-shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
        />
      </svg>

      {/* Main message */}
      <span className="flex-1 text-warning font-medium">
        Verify your email to unlock the proxy gateway. Check your inbox at{' '}
        <strong className="font-semibold">{user.email}</strong>
        {' '}or{' '}

        {resendState === 'sent' ? (
          <span className="text-success font-semibold">Email sent!</span>
        ) : (
          <button
            type="button"
            onClick={handleResend}
            disabled={resendState === 'loading'}
            className="underline underline-offset-2 font-semibold text-warning hover:text-warning-text transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {resendState === 'loading' ? 'Sending…' : 'Resend email'}
          </button>
        )}

        {resendState === 'error' && errorMsg && (
          <span className="ml-2 text-error text-xs">({errorMsg})</span>
        )}
      </span>

      {/* Dismiss button */}
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss verification banner"
        className="ml-auto flex-shrink-0 text-warning/60 hover:text-warning transition-colors"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  )
}

export default VerificationBanner
