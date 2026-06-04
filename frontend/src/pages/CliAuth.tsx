/**
 * Arbiter — CLI Authorization page.
 *
 * Route: /cli-auth?code=WORD-NNNN (no sidebar)
 *
 * Lets a logged-in user approve or deny a pending CLI device authorization.
 * The user_code is read from the `code` query param and displayed for visual
 * verification before the user commits to granting CLI access.
 *
 * States:
 *   loading   — auth context is still hydrating
 *   ready     — show code + Authorize / Deny buttons
 *   success   — approved; user can close the tab
 *   cancelled — user clicked Deny
 *   error     — code not found (404), expired (410), already used (409), or invalid URL
 */

import React, { useEffect, useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { authClient } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { ArbiterMark } from '../components/ArbiterLogo'

// ── Types ─────────────────────────────────────────────────────────────────────

type PageState = 'loading' | 'ready' | 'success' | 'cancelled' | 'error'

interface ApproveResponse {
  detail: string
}

// ── Component ─────────────────────────────────────────────────────────────────

function CliAuth(): React.ReactElement {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { user, isLoading: authLoading } = useAuth()

  const code = searchParams.get('code') ?? ''

  const [state, setState] = useState<PageState>('loading')
  const [errorMessage, setErrorMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Redirect to login if unauthenticated once the auth context has resolved
  useEffect(() => {
    if (authLoading) return

    if (!user) {
      const next = encodeURIComponent(`/cli-auth?code=${encodeURIComponent(code)}`)
      void navigate(`/login?redirect=${next}`, { replace: true })
      return
    }

    if (!code) {
      setErrorMessage('No authorization code found in the URL. Please run `arbiter login` again.')
      setState('error')
      return
    }

    setState('ready')
  }, [authLoading, user, code, navigate])

  async function handleAuthorize(): Promise<void> {
    if (!code || isSubmitting) return
    setIsSubmitting(true)

    try {
      await authClient.patch<ApproveResponse>(
        `/auth/cli/device/${encodeURIComponent(code)}/approve`,
      )
      setState('success')
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status

      if (status === 410) {
        setErrorMessage('This code has expired. Please run `arbiter login` again.')
      } else if (status === 409) {
        setErrorMessage('This code has already been used. Please run `arbiter login` again.')
      } else if (status === 404) {
        setErrorMessage('Authorization code not found. Please run `arbiter login` again.')
      } else {
        setErrorMessage('Something went wrong. Please run `arbiter login` again.')
      }

      setState('error')
    } finally {
      setIsSubmitting(false)
    }
  }

  async function handleDeny(): Promise<void> {
    if (isSubmitting) return
    setIsSubmitting(true)

    try {
      await authClient.patch<ApproveResponse>(
        `/auth/cli/device/${encodeURIComponent(code)}/deny`,
      )
    } catch {
      // Best-effort — the code will expire naturally; show cancelled state regardless
    } finally {
      setIsSubmitting(false)
    }

    setState('cancelled')
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-base flex items-center justify-center relative overflow-hidden px-4">
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

      <div className="relative w-full max-w-sm animate-fade-in">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-8">
          <ArbiterMark size={28} />
          <span className="text-primary font-semibold text-lg tracking-tight">Arbiter</span>
        </div>

        <div className="bg-surface/85 backdrop-blur-xl border border-border rounded-2xl p-8 shadow-2xl">
          {/* ── Loading ──────────────────────────────────────────────────── */}
          {state === 'loading' && (
            <div className="flex flex-col items-center gap-4 py-4">
              <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
              <p className="text-secondary text-sm">Loading…</p>
            </div>
          )}

          {/* ── Ready ────────────────────────────────────────────────────── */}
          {state === 'ready' && (
            <>
              <div className="text-center mb-7">
                <div className="w-12 h-12 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center mx-auto mb-4">
                  <svg
                    className="w-6 h-6 text-accent"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.75}
                      d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                </div>
                <h1 className="font-display text-xl font-semibold text-primary tracking-tight mb-1">
                  Authorize CLI Access
                </h1>
                <p className="text-secondary text-sm">
                  An Arbiter CLI session is requesting access to your account.
                </p>
              </div>

              {/* Code display */}
              <div className="bg-base border border-border rounded-xl px-5 py-4 mb-6 text-center">
                <p className="text-xs font-semibold text-muted uppercase tracking-widest mb-2">
                  Authorization Code
                </p>
                <p className="font-mono text-2xl font-bold text-primary tracking-widest">
                  {code}
                </p>
                <p className="text-xs text-muted mt-2">
                  Confirm this matches the code in your terminal.
                </p>
              </div>

              {/* Scoping note */}
              <p className="text-xs text-secondary text-center mb-6">
                This will grant CLI access to your organization as{' '}
                <span className="text-primary font-medium">{user?.email}</span>.
              </p>

              {/* Actions */}
              <div className="flex flex-col gap-2.5">
                <button
                  type="button"
                  onClick={() => void handleAuthorize()}
                  disabled={isSubmitting}
                  className="press w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover-glow-standard"
                >
                  {isSubmitting ? 'Authorizing…' : 'Authorize'}
                </button>

                <button
                  type="button"
                  onClick={() => void handleDeny()}
                  disabled={isSubmitting}
                  className="press w-full bg-transparent hover:bg-error/8 disabled:opacity-50 disabled:cursor-not-allowed text-error border border-error/30 hover:border-error/50 font-semibold text-sm py-2.5 rounded-lg transition-all duration-150"
                >
                  Deny
                </button>
              </div>
            </>
          )}

          {/* ── Success ──────────────────────────────────────────────────── */}
          {state === 'success' && (
            <div className="text-center py-2">
              <div className="w-12 h-12 rounded-full bg-success/10 border border-success/20 flex items-center justify-center mx-auto mb-4">
                <svg
                  className="w-6 h-6 text-success"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              <h1 className="font-display text-lg font-semibold text-primary mb-2">
                CLI authorized
              </h1>
              <p className="text-secondary text-sm">
                You can close this tab. Return to your terminal.
              </p>
            </div>
          )}

          {/* ── Cancelled ────────────────────────────────────────────────── */}
          {state === 'cancelled' && (
            <div className="text-center py-2">
              <div className="w-12 h-12 rounded-full bg-muted/10 border border-border flex items-center justify-center mx-auto mb-4">
                <svg
                  className="w-6 h-6 text-muted"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
              <h1 className="font-display text-lg font-semibold text-primary mb-2">
                Authorization denied
              </h1>
              <p className="text-secondary text-sm">
                The CLI session was not granted access. You can close this tab.
              </p>
            </div>
          )}

          {/* ── Error ────────────────────────────────────────────────────── */}
          {state === 'error' && (
            <div className="text-center py-2">
              <div className="w-12 h-12 rounded-full bg-error/10 border border-error/20 flex items-center justify-center mx-auto mb-4">
                <svg
                  className="w-6 h-6 text-error"
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
              </div>
              <h1 className="font-display text-lg font-semibold text-primary mb-2">
                Authorization failed
              </h1>
              <p className="text-secondary text-sm">{errorMessage}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default CliAuth
