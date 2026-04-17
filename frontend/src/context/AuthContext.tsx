/**
 * Nexvault — Auth context.
 *
 * Provides JWT-based authentication state for the dashboard UI.
 * Agent API key auth remains separate (apiClient in api/client.ts).
 *
 * Storage keys:
 *   nexvault_access_token  — JWT (24h)
 *   nexvault_refresh_token — opaque rt_<64hex> (30d)
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { authClient } from '../api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AuthUser {
  id: string
  email: string
  role: string
  org_id: string
  org_name: string
  org_plan: string
}

export interface AuthState {
  user: AuthUser | null
  accessToken: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  register: (orgName: string, email: string, password: string, inviteCode?: string) => Promise<void>
  refreshUser: () => Promise<void>
}

// ── Context ───────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthState | null>(null)

// ── Storage helpers ───────────────────────────────────────────────────────────

const ACCESS_KEY = 'nexvault_access_token'
const REFRESH_KEY = 'nexvault_refresh_token'

function storeTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access)
  localStorage.setItem(REFRESH_KEY, refresh)
}

function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

// ── Provider ──────────────────────────────────────────────────────────────────

interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

interface MeResponse {
  id: string
  email: string
  role: string
  org_id: string
  org_name: string
  org_plan: string
}

export function AuthProvider({ children }: { children: React.ReactNode }): React.ReactElement {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(
    localStorage.getItem(ACCESS_KEY)
  )
  const [isLoading, setIsLoading] = useState(true)

  // Hydrate user from stored access token on mount
  useEffect(() => {
    const stored = localStorage.getItem(ACCESS_KEY)
    if (!stored) {
      setIsLoading(false)
      return
    }

    authClient
      .get<MeResponse>('/auth/me')
      .then((r) => {
        setUser(r.data)
        setAccessToken(stored)
      })
      .catch(async () => {
        // Access token failed — attempt refresh
        const refresh = localStorage.getItem(REFRESH_KEY)
        if (!refresh) {
          clearTokens()
          setUser(null)
          setAccessToken(null)
          setIsLoading(false)
          return
        }
        try {
          const res = await authClient.post<TokenResponse>('/auth/refresh', {
            refresh_token: refresh,
          })
          storeTokens(res.data.access_token, res.data.refresh_token)
          setAccessToken(res.data.access_token)
          // Re-fetch user with new token
          const me = await authClient.get<MeResponse>('/auth/me')
          setUser(me.data)
        } catch {
          clearTokens()
          setUser(null)
          setAccessToken(null)
        }
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [])

  const refreshUser = useCallback(async (): Promise<void> => {
    const stored = localStorage.getItem(ACCESS_KEY)
    if (!stored) {
      setUser(null)
      setAccessToken(null)
      return
    }
    try {
      const me = await authClient.get<MeResponse>('/auth/me')
      setUser(me.data)
      setAccessToken(stored)
    } catch {
      clearTokens()
      setUser(null)
      setAccessToken(null)
    }
  }, [])

  const login = useCallback(async (email: string, password: string): Promise<void> => {
    const res = await authClient.post<TokenResponse>('/auth/login', { email, password })
    storeTokens(res.data.access_token, res.data.refresh_token)
    setAccessToken(res.data.access_token)
    const me = await authClient.get<MeResponse>('/auth/me')
    setUser(me.data)
  }, [])

  const logout = useCallback(async (): Promise<void> => {
    try {
      await authClient.post('/auth/logout')
    } catch {
      // Best-effort — clear locally regardless
    }
    clearTokens()
    setUser(null)
    setAccessToken(null)
  }, [])

  const register = useCallback(
    async (orgName: string, email: string, password: string, inviteCode = ''): Promise<void> => {
      const res = await authClient.post<TokenResponse>('/auth/register', {
        org_name: orgName,
        email,
        password,
        invite_code: inviteCode,
      })
      storeTokens(res.data.access_token, res.data.refresh_token)
      setAccessToken(res.data.access_token)
      const me = await authClient.get<MeResponse>('/auth/me')
      setUser(me.data)
    },
    []
  )

  return (
    <AuthContext.Provider value={{ user, accessToken, isLoading, login, logout, register, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
