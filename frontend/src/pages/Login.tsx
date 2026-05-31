/**
 * Arbiter — Login page.
 *
 * Route: /login (public, no sidebar)
 * On success: navigates to / or /onboarding (if onboarding incomplete).
 */

import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authClient } from '../api/client'
import { ArbiterMark } from '../components/ArbiterLogo'

interface ProvidersResponse {
  google: boolean
  github: boolean
}

const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://localhost:8000/api/v1'

function Login(): React.ReactElement {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [providers, setProviders] = useState<ProvidersResponse>({ google: false, github: false })

  useEffect(() => {
    if (searchParams.get('error') === 'sso_failed') {
      setError('Social login failed. Please try again.')
    }
    if (searchParams.get('reset') === '1') {
      setSuccess('Password reset successfully. Sign in with your new password.')
    }
  }, [searchParams])

  useEffect(() => {
    authClient
      .get<ProvidersResponse>('/auth/providers')
      .then((r) => setProviders(r.data))
      .catch(() => {})
  }, [])

  const handleSubmit = async (e: React.FormEvent): Promise<void> => {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)

    try {
      await login(email.trim(), password)

      navigate('/')
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 401) {
        setError('Invalid email or password.')
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-base flex items-center justify-center relative overflow-hidden">
      {/* Background glows */}
      <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-accent/10 blur-[120px] pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-teal/8 blur-[120px] pointer-events-none" />

      {/* Dot grid texture */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.035]"
        style={{
          backgroundImage: 'radial-gradient(circle, #8B1A6B 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      />

      <div className="relative w-full max-w-sm px-4 animate-fade-in">
        {/* Card */}
        <div className="bg-surface/85 backdrop-blur-xl border border-border-strong rounded-2xl p-8 shadow-2xl">
          {/* Wordmark */}
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-3 mb-2">
              <ArbiterMark size={36} />
              <span className="font-display text-primary font-semibold text-3xl tracking-tight">Arbiter</span>
            </div>
            <p className="text-secondary text-sm mt-2">The identity layer for your AI agents</p>
          </div>

          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
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
                placeholder="you@example.com"
                className="w-full bg-base border border-border-strong text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-[border-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] placeholder:text-muted"
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
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-base border border-border-strong text-primary text-sm px-3.5 py-2.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-[border-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] placeholder:text-muted"
              />
            </div>

            <div className="flex justify-end -mt-1">
              <Link to="/forgot-password" className="text-xs text-accent-light hover:text-primary transition-colors">
                Forgot password?
              </Link>
            </div>

            {success && (
              <div className="flex items-center gap-2 bg-success/8 border border-success/20 rounded-lg px-3 py-2">
                <span className="w-1.5 h-1.5 rounded-full bg-success flex-shrink-0" />
                <p className="text-success text-xs">{success}</p>
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
              {isSubmitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="text-center text-xs text-secondary mt-5">
            Don't have an account?{' '}
            <Link to="/register" className="text-accent-light hover:text-primary font-medium transition-colors">
              Create one
            </Link>
          </p>

          {(providers.google || providers.github) && (
            <>
              <div className="flex items-center gap-3 mt-5">
                <div className="flex-1 border-t border-border" />
                <span className="text-secondary text-xs font-medium">or continue with</span>
                <div className="flex-1 border-t border-border" />
              </div>

              <div className="flex flex-col gap-2 mt-4">
                {providers.google && (
                  <a href={`${API_BASE}/auth/google`}>
                    <button
                      type="button"
                      className="press w-full border border-border-strong bg-elevated/60 hover:bg-elevated hover:border-border-strong text-primary font-medium text-sm py-2.5 px-4 rounded-lg flex items-center gap-3 transition-[background-color,border-color] duration-150 ease-[var(--ease-out-expo)]"
                    >
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
                    <button
                      type="button"
                      className="press w-full border border-border-strong bg-elevated/60 hover:bg-elevated hover:border-border-strong text-primary font-medium text-sm py-2.5 px-4 rounded-lg flex items-center gap-3 transition-[background-color,border-color] duration-150 ease-[var(--ease-out-expo)]"
                    >
                      <svg width="18" height="18" viewBox="0 0 16 16" aria-hidden="true" fill="currentColor">
                        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
                      </svg>
                      Continue with GitHub
                    </button>
                  </a>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default Login
