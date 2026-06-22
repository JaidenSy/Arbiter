import React, { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authClient } from '../api/client'

// ── Icons ─────────────────────────────────────────────────────────────────────

const GoogleIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
)

const GitHubIcon = (): React.ReactElement => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0 1 12 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
  </svg>
)

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }): React.ReactElement {
  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-border">
        <h2 className="text-sm font-semibold text-primary">{title}</h2>
      </div>
      <div className="p-6">{children}</div>
    </div>
  )
}

// ── Field row ─────────────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }): React.ReactElement {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-6">
      <label className="text-xs text-secondary font-medium w-32 shrink-0">{label}</label>
      <div className="flex-1">{children}</div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function Account(): React.ReactElement {
  const { user, refreshUser, logout } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [resendingVerification, setResendingVerification] = useState(false)
  const [resendMsg, setResendMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Social linking state
  const [linkingProvider, setLinkingProvider] = useState<string | null>(null)
  const [unlinkingProvider, setUnlinkingProvider] = useState<string | null>(null)
  const [linkMsg, setLinkMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Detect redirect back from OAuth link flow
  useEffect(() => {
    const linked = searchParams.get('linked')
    const linkError = searchParams.get('link_error')
    if (linked) {
      setLinkMsg({ type: 'success', text: `${linked.charAt(0).toUpperCase() + linked.slice(1)} account linked successfully.` })
      void refreshUser()
      setSearchParams({}, { replace: true })
    } else if (linkError) {
      setLinkMsg({ type: 'error', text: linkError })
      setSearchParams({}, { replace: true })
    }
  }, [searchParams, refreshUser, setSearchParams])

  // Profile form
  const [displayName, setDisplayName] = useState(user?.display_name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileMsg, setProfileMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Password form
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [pwSaving, setPwSaving] = useState(false)
  const [pwMsg, setPwMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Delete confirmation
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  if (!user) return <></>

  const initials = (user.display_name ?? user.email)[0]?.toUpperCase() ?? '?'

  // ── Handlers ────────────────────────────────────────────────────────────────

  async function handleResendVerification(): Promise<void> {
    setResendingVerification(true)
    setResendMsg(null)
    try {
      await authClient.post('/auth/send-verification')
      setResendMsg({ type: 'success', text: 'Verification email sent. Check your inbox.' })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setResendMsg({ type: 'error', text: msg ?? 'Failed to send verification email.' })
    } finally {
      setResendingVerification(false)
    }
  }

  async function handleProfileSave(e: React.FormEvent): Promise<void> {
    e.preventDefault()
    setProfileSaving(true)
    setProfileMsg(null)
    const emailChanged = email !== user!.email
    try {
      const res = await authClient.patch<{ pending_email_confirmation?: string | null }>('/auth/me', {
        display_name: displayName.trim() || null,
        email: emailChanged ? email : undefined,
      })
      await refreshUser()
      if (emailChanged && res.data.pending_email_confirmation) {
        setEmail(user!.email) // reset field back to current confirmed email
        setProfileMsg({ type: 'success', text: `Check ${res.data.pending_email_confirmation} for a confirmation link. Your email won't change until you click it.` })
      } else {
        setProfileMsg({ type: 'success', text: 'Profile updated.' })
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setProfileMsg({ type: 'error', text: msg ?? 'Failed to update profile.' })
    } finally {
      setProfileSaving(false)
    }
  }

  async function handlePasswordChange(e: React.FormEvent): Promise<void> {
    e.preventDefault()
    if (newPw !== confirmPw) {
      setPwMsg({ type: 'error', text: 'Passwords do not match.' })
      return
    }
    setPwSaving(true)
    setPwMsg(null)
    try {
      await authClient.post('/auth/me/change-password', {
        current_password: currentPw,
        new_password: newPw,
      })
      setCurrentPw('')
      setNewPw('')
      setConfirmPw('')
      setPwMsg({ type: 'success', text: 'Password updated.' })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setPwMsg({ type: 'error', text: msg ?? 'Failed to update password.' })
    } finally {
      setPwSaving(false)
    }
  }

  async function handleLinkProvider(provider: string): Promise<void> {
    setLinkingProvider(provider)
    setLinkMsg(null)
    try {
      const res = await authClient.post<{ redirect_url: string }>('/auth/sso/link/initiate', { provider })
      // Navigate top-level window to start the OAuth dance
      window.location.href = res.data.redirect_url
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setLinkMsg({ type: 'error', text: msg ?? 'Failed to start link flow.' })
      setLinkingProvider(null)
    }
  }

  async function handleUnlinkProvider(provider: string): Promise<void> {
    setUnlinkingProvider(provider)
    setLinkMsg(null)
    try {
      await authClient.delete(`/auth/sso/link?provider=${provider}`)
      await refreshUser()
      setLinkMsg({ type: 'success', text: `${provider.charAt(0).toUpperCase() + provider.slice(1)} account unlinked.` })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setLinkMsg({ type: 'error', text: msg ?? 'Failed to unlink account.' })
    } finally {
      setUnlinkingProvider(null)
    }
  }

  async function handleDeleteAccount(): Promise<void> {
    setDeleteLoading(true)
    setDeleteError(null)
    try {
      await authClient.delete('/auth/me')
      await logout()
      navigate('/login')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setDeleteError(msg ?? 'Failed to delete account. Please try again.')
      setDeleteLoading(false)
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-2xl mx-auto px-6 py-10 space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight text-primary">My Account</h1>
        <p className="text-secondary text-sm mt-1">Manage your profile, security, and account settings.</p>
      </div>

      {/* ── Unverified email banner ── */}
      {!user.is_verified && (
        <div className="flex items-start gap-3 bg-warning/8 border border-warning/20 rounded-xl px-4 py-3">
          <svg className="w-4 h-4 text-warning mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
          <div className="flex-1 min-w-0">
            <p className="text-warning text-sm font-medium">Email not verified</p>
            <p className="text-warning/70 text-xs mt-0.5">Verify your email to unlock plan upgrades and secure your account.</p>
            {resendMsg && (
              <p className={`text-xs mt-1.5 ${resendMsg.type === 'success' ? 'text-success' : 'text-error'}`}>
                {resendMsg.text}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => void handleResendVerification()}
            disabled={resendingVerification}
            className="shrink-0 text-xs font-medium text-warning hover:text-white border border-warning/30 hover:border-warning/60 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
          >
            {resendingVerification ? 'Sending…' : 'Resend'}
          </button>
        </div>
      )}

      {/* ── Profile ── */}
      <Section title="Profile">
        <form onSubmit={(e) => void handleProfileSave(e)} className="space-y-5">
          {/* Avatar */}
          <div className="flex items-center gap-4 pb-4 border-b border-border">
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt="Avatar"
                className="w-12 h-12 rounded-full border border-border-strong"
              />
            ) : (
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-accent/30 to-teal/20 border border-accent/40 flex items-center justify-center text-accent-light font-mono font-semibold text-lg">
                {initials}
              </div>
            )}
            <div>
              <p className="text-sm font-medium text-primary">{user.display_name ?? user.email.split('@')[0]}</p>
              <p className="text-xs text-secondary capitalize">{user.role} · {user.org_name}</p>
            </div>
          </div>

          <Field label="Display name">
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your name"
              maxLength={64}
              className="w-full bg-base border border-border rounded-lg px-3 py-2 text-sm text-primary placeholder:text-muted focus:outline-none focus:border-accent/50 transition-colors"
            />
          </Field>

          <Field label="Email">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-base border border-border rounded-lg px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent/50 transition-colors"
            />
          </Field>

          {profileMsg && (
            <p className={`text-xs ${profileMsg.type === 'success' ? 'text-success' : 'text-error'}`}>
              {profileMsg.text}
            </p>
          )}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={profileSaving}
              className="px-4 py-2 text-sm bg-accent hover:bg-accent/80 disabled:opacity-50 text-white rounded-lg transition-colors"
            >
              {profileSaving ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </form>
      </Section>

      {/* ── Security ── */}
      {user.has_password && (
        <Section title="Security">
          <form onSubmit={(e) => void handlePasswordChange(e)} className="space-y-4">
            <Field label="Current password">
              <input
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full bg-base border border-border rounded-lg px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent/50 transition-colors"
              />
            </Field>

            <Field label="New password">
              <input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                className="w-full bg-base border border-border rounded-lg px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent/50 transition-colors"
              />
            </Field>

            <Field label="Confirm password">
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                required
                autoComplete="new-password"
                className="w-full bg-base border border-border rounded-lg px-3 py-2 text-sm text-primary focus:outline-none focus:border-accent/50 transition-colors"
              />
            </Field>

            {pwMsg && (
              <p className={`text-xs ${pwMsg.type === 'success' ? 'text-success' : 'text-error'}`}>
                {pwMsg.text}
              </p>
            )}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={pwSaving}
                className="px-4 py-2 text-sm bg-accent hover:bg-accent/80 disabled:opacity-50 text-white rounded-lg transition-colors"
              >
                {pwSaving ? 'Updating…' : 'Update Password'}
              </button>
            </div>
          </form>
        </Section>
      )}

      {/* ── Connected Accounts ── */}
      <Section title="Connected Accounts">
        <div className="space-y-3">
          {(['google', 'github'] as const).map((provider) => {
            const linked = user.linked_providers.includes(provider)
            const isLinking = linkingProvider === provider
            const isUnlinking = unlinkingProvider === provider
            return (
              <div key={provider} className="flex items-center justify-between py-2">
                <div className="flex items-center gap-3">
                  <span className="text-secondary">
                    {provider === 'google' ? <GoogleIcon /> : <GitHubIcon />}
                  </span>
                  <div>
                    <span className="text-sm text-primary capitalize">{provider}</span>
                    {linked && (
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full bg-success/10 text-success border border-success/20 font-medium">
                        Connected
                      </span>
                    )}
                  </div>
                </div>
                {linked ? (
                  <button
                    type="button"
                    onClick={() => void handleUnlinkProvider(provider)}
                    disabled={isUnlinking}
                    className="text-xs text-secondary hover:text-error border border-border hover:border-error/30 hover:bg-error/8 px-3 py-1.5 rounded-lg transition-all disabled:opacity-50"
                  >
                    {isUnlinking ? 'Unlinking…' : 'Unlink'}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => void handleLinkProvider(provider)}
                    disabled={isLinking}
                    className="text-xs text-secondary hover:text-accent-light border border-border hover:border-accent/40 hover:bg-accent/8 px-3 py-1.5 rounded-lg transition-all disabled:opacity-50"
                  >
                    {isLinking ? 'Redirecting…' : 'Link'}
                  </button>
                )}
              </div>
            )
          })}
          {linkMsg && (
            <p className={`text-xs pt-1 ${linkMsg.type === 'success' ? 'text-success' : 'text-error'}`}>
              {linkMsg.text}
            </p>
          )}
        </div>
      </Section>

      {/* ── Danger Zone ── */}
      <Section title="Danger Zone">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-primary">Delete account</p>
            <p className="text-xs text-secondary mt-1">
              Permanently deactivates your account and revokes all active sessions. This cannot be undone.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowDeleteConfirm(true)}
            className="shrink-0 px-4 py-2 text-sm border border-error/40 text-error hover:bg-error/10 rounded-lg transition-colors"
          >
            Delete Account
          </button>
        </div>
      </Section>

      {/* ── Delete confirmation modal ── */}
      {showDeleteConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-account-title"
          className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        >
          <div className="bg-overlay border border-border-strong rounded-xl shadow-2xl p-6 w-full max-w-sm">
            <h3 id="delete-account-title" className="text-base font-semibold text-primary mb-2">Delete your account?</h3>
            <p className="text-sm text-secondary mb-4">
              This will immediately deactivate your account and sign you out everywhere. This action cannot be undone.
            </p>
            <p className="text-xs text-warning/80 bg-warning/5 border border-warning/20 rounded-lg px-3 py-2 mb-4">
              Your Stripe subscription will be cancelled immediately upon deletion.
            </p>
            {deleteError && (
              <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2 mb-4">
                <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
                <p className="text-error text-xs">{deleteError}</p>
              </div>
            )}
            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={() => { setShowDeleteConfirm(false); setDeleteError(null); }}
                className="px-4 py-2 text-sm text-secondary hover:text-primary border border-border hover:border-border-strong rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleDeleteAccount()}
                disabled={deleteLoading}
                className="px-4 py-2 text-sm bg-error hover:bg-error/80 disabled:opacity-50 text-white rounded-lg transition-colors"
              >
                {deleteLoading ? 'Deleting…' : 'Yes, delete it'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
