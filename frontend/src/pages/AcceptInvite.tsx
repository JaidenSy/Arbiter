/**
 * Arbiter — Accept Invite page.
 *
 * Route: /accept-invite?token=<token> (public, no sidebar)
 *
 * Three paths into POST /auth/accept-invite:
 *   - Signed in            → join the org with the existing account (no form)
 *   - No account yet       → create-account form (original flow)
 *   - Account exists, not  → inline sign-in, then the join is retried
 *     signed in              automatically
 *
 * On success the backend returns a fresh token pair with the new org active;
 * we store it and hard-reload so every org-scoped view rehydrates.
 */

import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArbiterMark } from '../components/ArbiterLogo'
import PasswordRequirements from '../components/PasswordRequirements'
import { isPasswordValid } from '../utils/password'
import { authClient } from '../api/client'
import { useAuth } from '../context/AuthContext'

const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://localhost:8000/api/v1'

const ACCESS_KEY = 'arbiter_access_token'
const REFRESH_KEY = 'arbiter_refresh_token'

type Mode = 'create' | 'login'

interface AcceptResponse {
  access_token?: string
  refresh_token?: string
  detail?: string
}

interface InvitePreview {
  org_name: string
  plan_tier: string
  role: string
  email: string
}

function inputClass(): string {
  return 'w-full bg-base border border-border text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent/60 focus:border-accent/60 transition-all duration-150 placeholder:text-muted'
}

function ErrorNote({ message }: { message: string }): React.ReactElement {
  return (
    <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
      <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
      <p className="text-error text-xs">{message}</p>
    </div>
  )
}

function AcceptInvite(): React.ReactElement {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const { user, isLoading, login, logout } = useAuth()

  const [mode, setMode] = useState<Mode>('create')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [alreadyMember, setAlreadyMember] = useState(false)

  // Invite preview: fetched once on mount to populate the confirmation modal.
  const [invitePreview, setInvitePreview] = useState<InvitePreview | null>(null)
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  // Pending action to run after the user confirms the modal.
  const [pendingAction, setPendingAction] = useState<(() => Promise<void>) | null>(null)

  useEffect(() => {
    if (!token) return
    authClient
      .get<InvitePreview>(`/auth/invite-preview?token=${encodeURIComponent(token)}`)
      .then((res) => setInvitePreview(res.data))
      .catch(() => {
        // Preview is best-effort — a failure here doesn't block the flow.
      })
  }, [token])

  /**
   * Wrap an action so it first shows the ownership-disclosure modal.
   * The wrapped action is stored and executed only when the user confirms.
   */
  function withConfirmation(action: () => Promise<void>): () => Promise<void> {
    return async () => {
      setPendingAction(() => action)
      setShowConfirmModal(true)
    }
  }

  async function handleConfirm(): Promise<void> {
    setShowConfirmModal(false)
    if (pendingAction) {
      await pendingAction()
      setPendingAction(null)
    }
  }

  function storeAndEnter(data: AcceptResponse): void {
    if (data.access_token && data.refresh_token) {
      localStorage.setItem(ACCESS_KEY, data.access_token)
      localStorage.setItem(REFRESH_KEY, data.refresh_token)
      window.location.href = '/'
    }
  }

  // ── Signed-in path: join with the current account ─────────────────────────

  async function _doJoin(): Promise<void> {
    setError('')
    setIsSubmitting(true)
    try {
      const res = await authClient.post<AcceptResponse>('/auth/accept-invite', { token })
      storeAndEnter(res.data)
    } catch (err: unknown) {
      const response = (err as { response?: { status?: number; data?: { detail?: string } } })
        .response
      const detail = response?.data?.detail ?? 'Failed to accept invite.'
      if (response?.status === 409 && detail.includes('already a member')) {
        setAlreadyMember(true)
      } else if (response?.status === 422) {
        // The invite is addressed to an email with no account — it can't be
        // accepted by this session; the recipient must create that account.
        setError(
          'This invite was sent to a different email address. Sign out and open the link as its recipient.'
        )
      } else {
        setError(detail)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  /** Public entry-point for the signed-in join button — shows modal first. */
  const handleJoin = withConfirmation(_doJoin)

  // ── No-account path: create the invited account ───────────────────────────

  async function _doCreate(): Promise<void> {
    setError('')
    setIsSubmitting(true)
    try {
      // Raw fetch (no Authorization header): a stale stored token must not
      // turn this unauthenticated flow into a failing authenticated one.
      const res = await fetch(`${API_BASE}/auth/accept-invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          display_name: displayName || undefined,
          password,
        }),
      })
      const data = (await res.json().catch(() => ({}))) as AcceptResponse

      if (!res.ok) {
        const detail = data.detail ?? 'Failed to accept invite.'
        if (res.status === 409 && detail.includes('already exists')) {
          // The invited email already has an account — sign in to join.
          setMode('login')
          setError('')
          return
        }
        setError(detail)
        return
      }

      storeAndEnter(data)
    } catch {
      setError('Network error. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  /** Shows modal before creating the account. */
  async function handleCreate(e: React.FormEvent): Promise<void> {
    e.preventDefault()
    // Run validation synchronously so errors appear before the modal.
    if (!isPasswordValid(password)) { setError('Password does not meet all the requirements listed below.'); return }
    if (password !== confirm) { setError('Passwords do not match.'); return }
    setError('')
    // pendingAction reads state captured in the closure — no stale event.
    setPendingAction(() => _doCreate)
    setShowConfirmModal(true)
  }

  // ── Existing-account path: sign in, then join ─────────────────────────────

  async function _doLoginAndJoin(): Promise<void> {
    setError('')
    setIsSubmitting(true)
    try {
      await login(loginEmail, loginPassword)
    } catch {
      setError('Invalid email or password.')
      setIsSubmitting(false)
      return
    }
    try {
      const res = await authClient.post<AcceptResponse>('/auth/accept-invite', { token })
      storeAndEnter(res.data)
    } catch (err: unknown) {
      const response = (err as { response?: { status?: number; data?: { detail?: string } } })
        .response
      const detail = response?.data?.detail ?? 'Signed in, but joining the organization failed.'
      if (response?.status === 409 && detail.includes('already a member')) {
        setAlreadyMember(true)
      } else if (response?.status === 422) {
        setError(
          'This invite was sent to an email without an account — it must be accepted by its recipient.'
        )
      } else {
        setError(detail)
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  /** Shows modal before signing in and joining. */
  async function handleLoginAndJoin(e: React.FormEvent): Promise<void> {
    e.preventDefault()
    setError('')
    setPendingAction(() => _doLoginAndJoin)
    setShowConfirmModal(true)
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  if (!token) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-secondary text-sm">Invalid invite link.</p>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center gap-2">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="w-2 h-2 rounded-full bg-accent animate-pulse"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
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
          <p className="text-secondary text-sm">
            {user
              ? 'Join the organization with your existing account.'
              : mode === 'login'
                ? 'Sign in to join the team.'
                : 'Create your account to join the team.'}
          </p>
        </div>

        <div className="bg-surface/80 backdrop-blur-xl border border-border rounded-2xl p-8 shadow-2xl">
          {alreadyMember ? (
            <div className="text-center">
              <p className="text-secondary text-sm mb-4">
                You're already a member of this organization.
              </p>
              <a
                href="/"
                className="inline-block bg-accent hover:bg-accent-light text-white font-semibold text-sm py-2.5 px-5 rounded-lg transition-all duration-150"
              >
                Go to dashboard
              </a>
            </div>
          ) : user ? (
            <div className="flex flex-col gap-4">
              <p className="text-secondary text-sm text-center">
                Signed in as <span className="text-primary font-medium">{user.email}</span>
              </p>
              {error && <ErrorNote message={error} />}
              <button
                type="button"
                onClick={() => void handleJoin()}
                disabled={isSubmitting}
                className="w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-all duration-150 hover-glow-standard"
              >
                {isSubmitting ? 'Joining…' : 'Join organization'}
              </button>
              <button
                type="button"
                onClick={() => void logout()}
                className="text-muted hover:text-secondary text-xs transition-colors"
              >
                Not you? Sign out
              </button>
            </div>
          ) : mode === 'login' ? (
            <form onSubmit={(e) => void handleLoginAndJoin(e)} className="flex flex-col gap-4">
              <p className="text-secondary text-xs">
                An account with the invited email already exists. Sign in and we'll add the
                organization to it.
              </p>
              <div>
                <label htmlFor="loginEmail" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
                  Email
                </label>
                <input
                  id="loginEmail"
                  type="email"
                  required
                  autoComplete="email"
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  placeholder="you@company.com"
                  className={inputClass()}
                />
              </div>
              <div>
                <label htmlFor="loginPassword" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
                  Password
                </label>
                <input
                  id="loginPassword"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="••••••••"
                  className={inputClass()}
                />
              </div>

              {error && <ErrorNote message={error} />}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-all duration-150 hover-glow-standard mt-1"
              >
                {isSubmitting ? 'Signing in…' : 'Sign in & join'}
              </button>
              <button
                type="button"
                onClick={() => { setMode('create'); setError('') }}
                className="text-muted hover:text-secondary text-xs transition-colors"
              >
                ← Create a new account instead
              </button>
            </form>
          ) : (
            <form onSubmit={(e) => void handleCreate(e)} className="flex flex-col gap-4">
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
                  className={inputClass()}
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
                  className={inputClass()}
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
                  className={inputClass()}
                />
              </div>

              {error && <ErrorNote message={error} />}

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-all duration-150 hover-glow-standard mt-1"
              >
                {isSubmitting ? 'Creating account…' : 'Create account'}
              </button>
              <button
                type="button"
                onClick={() => { setMode('login'); setError('') }}
                className="text-muted hover:text-secondary text-xs transition-colors"
              >
                Already have an account? Sign in to join
              </button>
            </form>
          )}
        </div>
      </div>

      {/* Ownership disclosure modal — shown before any accept action. */}
      {showConfirmModal && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowConfirmModal(false)}
        >
          <div
            className="bg-surface border border-border-strong rounded-xl p-6 w-full max-w-sm shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-base font-bold text-primary mb-2">Before you join</h2>
            {invitePreview ? (
              <div className="mb-4">
                <p className="text-secondary text-sm mb-3">
                  Resources you create in{' '}
                  <span className="text-primary font-semibold">{invitePreview.org_name}</span>{' '}
                  (agents, secrets, MCP servers) belong to the org. If you leave, they stay with the
                  org owner.
                </p>
                <div className="flex items-center gap-2">
                  <span className="text-secondary text-xs">This org is on the</span>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider border ${
                      invitePreview.plan_tier === 'pro'
                        ? 'bg-accent/15 text-accent-light border-border-accent'
                        : invitePreview.plan_tier === 'enterprise'
                          ? 'bg-purple-500/15 text-purple-300 border-purple-500/30'
                          : 'bg-white/5 text-muted border-border'
                    }`}
                  >
                    {invitePreview.plan_tier}
                  </span>
                  <span className="text-secondary text-xs">plan.</span>
                </div>
              </div>
            ) : (
              <p className="text-secondary text-sm mb-4">
                Resources you create in this organization belong to the org. If you leave, they stay
                with the org owner.
              </p>
            )}
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setShowConfirmModal(false)}
                className="flex-1 border border-border text-secondary hover:text-primary text-sm font-medium py-2.5 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleConfirm()}
                className="flex-1 bg-accent hover:bg-accent-light text-white font-semibold text-sm py-2.5 rounded-lg transition-all"
              >
                I understand, join
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AcceptInvite
