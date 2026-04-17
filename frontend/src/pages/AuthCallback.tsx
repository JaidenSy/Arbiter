/**
 * NexVault — SSO Callback page.
 *
 * Route: /auth/callback (public)
 *
 * The backend redirects here after a successful OAuth2 flow with:
 *   ?token=ott_<hex>
 *
 * This page exchanges the one-time token (OTT) for a JWT + refresh token,
 * stores them, fetches /auth/me, then redirects to the app.
 *
 * On failure (missing token, expired OTT, backend error) it redirects to
 * /login?error=sso_failed so the user sees a clear error message.
 */

import React, { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { authClient } from '../api/client'
import { useAuth } from '../context/AuthContext'

const ACCESS_KEY = 'nexvault_access_token'
const REFRESH_KEY = 'nexvault_refresh_token'

interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

interface OnboardingStatus {
  complete: boolean
}

function AuthCallback(): React.ReactElement {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { refreshUser } = useAuth()
  const didRun = useRef(false)

  useEffect(() => {
    // Strict-mode safe — only run the exchange once.
    if (didRun.current) return
    didRun.current = true

    const token = params.get('token')
    const error = params.get('error')

    if (error || !token) {
      void navigate('/login?error=sso_failed', { replace: true })
      return
    }

    void (async () => {
      try {
        const res = await authClient.post<TokenResponse>('/auth/sso/exchange', { token })
        localStorage.setItem(ACCESS_KEY, res.data.access_token)
        localStorage.setItem(REFRESH_KEY, res.data.refresh_token)

        // Hydrate auth context so ProtectedRoute / RootRedirect see the user immediately
        await refreshUser()

        // Check onboarding status
        try {
          const onb = await authClient.get<OnboardingStatus>('/onboarding/status')
          if (!onb.data.complete) {
            void navigate('/onboarding', { replace: true })
            return
          }
        } catch {
          // /onboarding/status error → go to dashboard
        }

        void navigate('/', { replace: true })
      } catch {
        void navigate('/login?error=sso_failed', { replace: true })
      }
    })()
  }, [navigate, params, refreshUser])

  return (
    <div className="min-h-screen bg-base flex items-center justify-center font-mono">
      <div className="text-center space-y-4">
        <div className="flex gap-1 justify-center">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-2 h-2 rounded-full bg-accent animate-pulse"
              style={{ animationDelay: `${i * 150}ms` }}
            />
          ))}
        </div>
        <p className="text-secondary text-sm">Completing sign-in…</p>
      </div>
    </div>
  )
}

export default AuthCallback
