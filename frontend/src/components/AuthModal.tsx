/**
 * AuthModal — login + register forms rendered as a blurred overlay on Landing.
 * Replaces the standalone /login and /register full-page routes.
 */

import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authClient } from '../api/client'
import { ArbiterMark } from './ArbiterLogo'

export type AuthMode = 'login' | 'register'

interface OnboardingStatus { complete: boolean }
interface ProvidersResponse { google: boolean; github: boolean }

const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000/api/v1'

const inputClass =
  'w-full bg-base border border-border-strong text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-[border-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] placeholder:text-muted'
const labelClass =
  'block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest'

interface Props {
  initialMode: AuthMode
  onClose: () => void
}

export default function AuthModal({ initialMode, onClose }: Props): React.ReactElement {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [mode, setMode] = useState<AuthMode>(initialMode)

  // ── Login state ──────────────────────────────────────────────────────────────
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError]     = useState<string | null>(null)
  const [loginSuccess, setLoginSuccess] = useState<string | null>(null)
  const [loginSubmitting, setLoginSubmitting] = useState(false)
  const [providers, setProviders] = useState<ProvidersResponse>({ google: false, github: false })

  // ── Register state ───────────────────────────────────────────────────────────
  const [orgName, setOrgName]             = useState('')
  const [regEmail, setRegEmail]           = useState('')
  const [regPassword, setRegPassword]     = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [inviteCode, setInviteCode]       = useState('')
  const [regError, setRegError]           = useState<string | null>(null)
  const [regSubmitting, setRegSubmitting] = useState(false)

  const inviteRequired = import.meta.env.VITE_INVITE_REQUIRED === 'true'

  // Lock body scroll while modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  // Read search params for login feedback (SSO error, password reset)
  useEffect(() => {
    if (searchParams.get('error') === 'sso_failed') setLoginError('Social login failed. Please try again.')
    if (searchParams.get('reset') === '1') setLoginSuccess('Password reset successfully. Sign in with your new password.')
  }, [searchParams])

  useEffect(() => {
    authClient.get<ProvidersResponse>('/auth/providers').then((r) => setProviders(r.data)).catch(() => {})
  }, [])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent): void => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  // ── Handlers ─────────────────────────────────────────────────────────────────

  const handleLogin = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    setLoginError(null)
    setLoginSubmitting(true)
    try {
      await login(email.trim(), password)
      try {
        const res = await authClient.get<OnboardingStatus>('/onboarding/status')
        if (!res.data.complete) { navigate('/onboarding'); return }
      } catch { /* no onboarding endpoint — fall through */ }
      navigate('/')
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      setLoginError(status === 401 ? 'Invalid email or password.' : 'Something went wrong. Please try again.')
    } finally {
      setLoginSubmitting(false)
    }
  }

  const validateRegister = (): string | null => {
    if (!orgName.trim())             return 'Organization name is required.'
    if (!regEmail.trim())            return 'Email is required.'
    if (regPassword.length < 8)      return 'Password must be at least 8 characters.'
    if (regPassword !== confirmPassword) return 'Passwords do not match.'
    if (inviteRequired && !inviteCode.trim()) return 'An invite code is required.'
    return null
  }

  const handleRegister = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    const validationError = validateRegister()
    if (validationError) { setRegError(validationError); return }
    setRegError(null)
    setRegSubmitting(true)
    try {
      await register(orgName.trim(), regEmail.trim(), regPassword, inviteCode.trim())
      navigate('/onboarding')
    } catch (err: unknown) {
      const res = (err as { response?: { status?: number; data?: { detail?: string } } })?.response
      if (res?.status === 409) setRegError('An account with that email already exists.')
      else if (res?.data?.detail) setRegError(res.data.detail)
      else setRegError('Registration failed. Please try again.')
    } finally {
      setRegSubmitting(false)
    }
  }

  // ── OAuth buttons (shared) ───────────────────────────────────────────────────

  const oauthButtons = (providers.google || providers.github) && (
    <>
      <div className="flex items-center gap-3 mt-5">
        <div className="flex-1 border-t border-border" />
        <span className="text-secondary text-xs font-medium">or continue with</span>
        <div className="flex-1 border-t border-border" />
      </div>
      <div className="flex flex-col gap-2 mt-4">
        {providers.google && (
          <a href={`${API_BASE}/auth/google`}>
            <button type="button" className="press w-full border border-border-strong bg-elevated/60 hover:bg-elevated hover:border-white/[0.22] text-primary font-medium text-sm py-2.5 px-4 rounded-lg flex items-center gap-3 transition-[background-color,border-color] duration-150 ease-[var(--ease-out-expo)]">
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
                <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
                <path d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332z" fill="#FBBC05"/>
                <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
              </svg>
              Continue with Google
            </button>
          </a>
        )}
        {providers.github && (
          <a href={`${API_BASE}/auth/github`}>
            <button type="button" className="press w-full border border-border-strong bg-elevated/60 hover:bg-elevated hover:border-white/[0.22] text-primary font-medium text-sm py-2.5 px-4 rounded-lg flex items-center gap-3 transition-[background-color,border-color] duration-150 ease-[var(--ease-out-expo)]">
              <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
              </svg>
              Continue with GitHub
            </button>
          </a>
        )}
      </div>
    </>
  )

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Blurred backdrop — click to close */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal card */}
      <div className="relative w-full max-w-sm modal-enter">
        <div className="bg-surface/95 backdrop-blur-xl border border-border-strong rounded-2xl p-8 shadow-2xl">
          {/* Close button */}
          <button
            onClick={onClose}
            className="press absolute top-4 right-4 text-muted hover:text-primary transition-colors duration-150"
            aria-label="Close"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
              <path d="M12.854 3.146a.5.5 0 0 1 0 .708L8.707 8l4.147 4.146a.5.5 0 0 1-.708.708L8 8.707l-4.146 4.147a.5.5 0 0 1-.708-.708L7.293 8 3.146 3.854a.5.5 0 0 1 .708-.708L8 7.293l4.146-4.147a.5.5 0 0 1 .708 0z"/>
            </svg>
          </button>

          {/* Wordmark */}
          <div className="text-center mb-6">
            <div className="flex items-center justify-center gap-3 mb-2">
              <ArbiterMark size={32} />
              <span className="font-display text-primary font-semibold text-2xl tracking-tight">Arbiter</span>
            </div>
          </div>

          {/* Mode tabs */}
          <div className="flex rounded-lg bg-base/60 border border-border p-1 mb-6 gap-1">
            {(['login', 'register'] as AuthMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 text-xs font-semibold py-1.5 rounded-md transition-colors duration-150 ease-[var(--ease-out-expo)] capitalize ${
                  mode === m
                    ? 'bg-surface text-primary shadow-sm'
                    : 'text-muted hover:text-secondary'
                }`}
              >
                {m === 'login' ? 'Sign in' : 'Create account'}
              </button>
            ))}
          </div>

          {/* ── Login form ─────────────────────────────────────────────────── */}
          {mode === 'login' && (
            <form onSubmit={(e) => void handleLogin(e)} className="space-y-4">
              <div>
                <label htmlFor="login-email" className={labelClass}>Email</label>
                <input
                  id="login-email"
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
                <label htmlFor="login-password" className={labelClass}>Password</label>
                <input
                  id="login-password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className={inputClass}
                />
              </div>
              <div className="flex justify-end -mt-1">
                <Link to="/forgot-password" className="text-xs text-accent-light hover:text-primary transition-colors duration-150">
                  Forgot password?
                </Link>
              </div>
              {loginSuccess && (
                <div className="flex items-center gap-2 bg-success/8 border border-success/20 rounded-lg px-3 py-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-success flex-shrink-0" />
                  <p className="text-success text-xs">{loginSuccess}</p>
                </div>
              )}
              {loginError && (
                <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
                  <p className="text-error text-xs">{loginError}</p>
                </div>
              )}
              <button
                type="submit"
                disabled={loginSubmitting}
                className="press w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover:shadow-[0_0_20px_rgba(217,119,6,0.35)] mt-2"
              >
                {loginSubmitting ? 'Signing in…' : 'Sign in'}
              </button>
              {oauthButtons}
            </form>
          )}

          {/* ── Register form ──────────────────────────────────────────────── */}
          {mode === 'register' && (
            <form onSubmit={(e) => void handleRegister(e)} className="space-y-4">
              <div>
                <label htmlFor="reg-org" className={labelClass}>Organization Name</label>
                <input
                  id="reg-org"
                  type="text"
                  required
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  placeholder="Acme Corp"
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="reg-email" className={labelClass}>Email</label>
                <input
                  id="reg-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  placeholder="you@example.com"
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="reg-password" className={labelClass}>Password</label>
                <input
                  id="reg-password"
                  type="password"
                  required
                  autoComplete="new-password"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  placeholder="min 8 characters"
                  className={inputClass}
                />
              </div>
              <div>
                <label htmlFor="reg-confirm" className={labelClass}>Confirm Password</label>
                <input
                  id="reg-confirm"
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
                  <label htmlFor="reg-invite" className={labelClass}>Invite Code</label>
                  <input
                    id="reg-invite"
                    type="text"
                    required
                    value={inviteCode}
                    onChange={(e) => setInviteCode(e.target.value)}
                    placeholder="Enter your invite code"
                    className={inputClass}
                  />
                </div>
              )}
              {regError && (
                <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
                  <p className="text-error text-xs">{regError}</p>
                </div>
              )}
              <button
                type="submit"
                disabled={regSubmitting}
                className="press w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm py-2.5 rounded-lg transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover:shadow-[0_0_20px_rgba(217,119,6,0.35)] mt-2"
              >
                {regSubmitting ? 'Creating account…' : 'Create account'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
