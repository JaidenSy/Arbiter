/**
 * Arbiter — Settings page.
 *
 * Sections:
 *   - Gateway API Key (stored in localStorage)
 *   - Gateway URL (base URL for Axios client)
 *   - About (version, MCP spec, license)
 */

import React, { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authClient } from '../api/client'
import type { BillingStatus, CacheStats } from '../api/types'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import Toggle from '../components/Toggle'

const SUPPORT_EMAIL: string = import.meta.env.VITE_SUPPORT_EMAIL ?? 'support@arbiterai.dev'

// ── Usage progress bar ────────────────────────────────────────────────────────

function UsageBar({
  label,
  used,
  limit,
}: {
  label: string
  used: number
  limit: number | null
}): React.ReactElement {
  const pct = limit === null ? 0 : Math.min((used / limit) * 100, 100)
  const isNearLimit = limit !== null && pct >= 80
  const isAtLimit = limit !== null && pct >= 100

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs font-mono text-secondary">
        <span>{label}</span>
        <span
          className={
            isAtLimit
              ? 'text-error font-semibold'
              : isNearLimit
              ? 'text-warning font-semibold'
              : 'text-primary'
          }
        >
          {used.toLocaleString()} / {limit === null ? '∞' : limit.toLocaleString()}
        </span>
      </div>
      {limit !== null && (
        <div className="h-1.5 bg-elevated rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isAtLimit
                ? 'bg-error'
                : isNearLimit
                ? 'bg-warning'
                : 'bg-accent'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
    </div>
  )
}

// ── Section header ────────────────────────────────────────────────────────────

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }): React.ReactElement {
  return (
    <div className="mb-5">
      <h2 className="text-primary text-sm font-semibold">{title}</h2>
      {subtitle && <p className="text-secondary text-xs mt-0.5">{subtitle}</p>}
    </div>
  )
}

// ── Billing Section ───────────────────────────────────────────────────────────

function BillingSection(): React.ReactElement {
  const { user } = useAuth()
  const isVerified = user?.is_verified ?? true // default true to avoid flash on load
  const { data, isLoading, isError } = useQuery<BillingStatus>({
    queryKey: ['billing-status'],
    queryFn: () =>
      authClient.get<BillingStatus>('/billing/status').then((r) => r.data),
    staleTime: 60_000,
  })

  const checkoutMutation = useMutation({
    mutationFn: () =>
      authClient
        .post<{ url: string }>('/billing/checkout', {})
        .then((r) => r.data.url),
    onSuccess: (url) => {
      window.location.href = url
    },
  })

  const portalMutation = useMutation({
    mutationFn: () =>
      authClient
        .post<{ url: string }>('/billing/portal', {
          return_url: window.location.href,
        })
        .then((r) => r.data.url),
    onSuccess: (url) => {
      window.location.href = url
    },
  })

  return (
    <div>
      <SectionHeader title="Billing" subtitle="Manage your plan and usage limits" />

      {isLoading && (
        <div className="space-y-2 max-w-2xl">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="skeleton-shimmer h-6 rounded-lg" />
          ))}
        </div>
      )}

      {isError && (
        <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2 max-w-2xl">
          <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
          <p className="text-error text-sm">Failed to load billing status.</p>
        </div>
      )}

      {data && (
        <div className="max-w-2xl space-y-5">
          {/* Plan badge */}
          <div className="flex items-center gap-3">
            <span className="text-secondary text-xs font-mono">Current plan</span>
            <span
              className={`text-xs font-semibold px-2.5 py-1 rounded-full uppercase tracking-wider ${
                data.plan === 'enterprise'
                  ? 'bg-accent/15 text-accent-light border border-border-accent'
                  : data.plan === 'pro'
                  ? 'bg-teal/10 text-teal-light border border-teal/20'
                  : 'bg-accent/10 text-accent-light border border-accent/20'
              }`}
            >
              {data.plan}
            </span>
          </div>

          {/* Usage bars */}
          {data.plan !== 'enterprise' && (
            <div className="space-y-4 bg-surface border border-border rounded-xl p-5">
              <p className="text-xs font-semibold text-secondary uppercase tracking-widest mb-1">Usage</p>
              <UsageBar
                label="Tool calls this month"
                used={data.tool_calls_month}
                limit={data.tool_calls_limit}
              />
              <UsageBar
                label="Agents"
                used={data.agents_count}
                limit={data.agents_limit}
              />
              <UsageBar
                label="MCP Servers"
                used={data.servers_count}
                limit={data.servers_limit}
              />
              <UsageBar
                label="Vault secrets"
                used={data.vault_secrets_count}
                limit={data.vault_secrets_limit}
              />
            </div>
          )}

          {/* CTA buttons */}
          {data.plan === 'free' && (
            <div className="space-y-4">
              {!isVerified && (
                <div className="flex items-start gap-3 bg-warning/8 border border-warning/20 rounded-lg px-4 py-3">
                  <svg className="w-4 h-4 text-warning mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                  </svg>
                  <div>
                    <p className="text-warning text-xs font-medium">Email verification required</p>
                    <p className="text-warning/70 text-xs mt-0.5">
                      Verify your email before upgrading.{' '}
                      <Link to="/account" className="underline hover:text-warning">Go to Account</Link>
                    </p>
                  </div>
                </div>
              )}

              {/* Pro comparison card */}
              <div className="bg-surface border border-accent/20 rounded-xl p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-semibold text-primary">Pro — $29 / month</p>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-accent/15 text-accent-light border border-accent/25 uppercase tracking-wider">Most popular</span>
                </div>
                <ul className="space-y-1.5">
                  {([
                    ['Agents', '2 → 25'],
                    ['MCP Servers', '3 → 50'],
                    ['Tool calls / mo', '5K → 100K'],
                    ['Vault secrets', '10 → 100'],
                    ['Team members', '3 → unlimited'],
                    ['Semantic cache', 'exact-match → AI similarity'],
                  ] as const).map(([label, delta]) => (
                    <li key={label} className="flex items-center justify-between text-xs">
                      <span className="text-secondary">{label}</span>
                      <span className="font-mono text-accent-light">{delta}</span>
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  disabled={checkoutMutation.isPending || !isVerified}
                  onClick={() => checkoutMutation.mutate()}
                  className="w-full bg-accent hover:bg-accent-light disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold px-5 py-2 rounded-lg transition-all hover-glow-standard"
                >
                  {checkoutMutation.isPending ? 'Redirecting…' : 'Upgrade to Pro'}
                </button>
              </div>

              <p className="text-secondary text-xs">
                Need unlimited scale, SSO, or a custom SLA?{' '}
                <a
                  href={`mailto:${SUPPORT_EMAIL}?subject=Arbiter Enterprise`}
                  className="text-accent-light hover:text-white transition-colors underline underline-offset-2"
                >
                  Talk to us about Enterprise →
                </a>
              </p>
            </div>
          )}

          {data.plan === 'pro' && (
            <div className="space-y-3">
              <button
                type="button"
                disabled={portalMutation.isPending}
                onClick={() => portalMutation.mutate()}
                className="bg-elevated hover:bg-white/[0.07] border border-border-strong hover:border-border-strong text-primary text-sm font-medium px-5 py-2 rounded-lg transition-all"
              >
                {portalMutation.isPending ? 'Redirecting…' : 'Manage Subscription'}
              </button>
              <p className="text-secondary text-xs">
                Need unlimited scale, SSO, or a dedicated SLA?{' '}
                <a
                  href={`mailto:${SUPPORT_EMAIL}?subject=Arbiter Enterprise`}
                  className="text-accent-light hover:text-white transition-colors underline underline-offset-2"
                >
                  Talk to us about Enterprise →
                </a>
              </p>
            </div>
          )}

          {data.plan === 'enterprise' && (
            <p className="text-secondary text-sm">
              Enterprise plan —{' '}
              <a
                href={`mailto:${SUPPORT_EMAIL}?subject=Arbiter Enterprise Subscription`}
                className="text-accent-light hover:text-white transition-colors"
              >
                contact us
              </a>{' '}
              to manage your subscription.
            </p>
          )}

          {(checkoutMutation.isError || portalMutation.isError) && (
            <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2">
              <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
              <p className="text-error text-xs">Billing action failed. Please try again.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── API Key Section ───────────────────────────────────────────────────────────

function ApiKeySection(): React.ReactElement {
  const [apiKey, setApiKey] = useState<string>(
    localStorage.getItem('arbiter_api_key') ?? '',
  )
  const [showKey, setShowKey] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = (): void => {
    localStorage.setItem('arbiter_api_key', apiKey)
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  const handleClear = (): void => {
    localStorage.removeItem('arbiter_api_key')
    setApiKey('')
  }

  const hasKey = apiKey.length > 0

  return (
    <div>
      <SectionHeader title="API Key" subtitle="Gateway key stored locally in your browser" />
      <div className="max-w-2xl space-y-4">
        <div>
          <label htmlFor="api-key-input" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
            Gateway API Key
          </label>
          <p className="text-secondary text-xs mb-2.5">
            Required to authenticate agent requests with the Arbiter gateway.
          </p>
          <div className="flex gap-2">
            <input
              id="api-key-input"
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="nx_..."
              className="flex-1 bg-base border border-border-strong text-primary text-sm font-mono px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              className="text-secondary hover:text-primary bg-elevated hover:bg-white/[0.07] border border-border hover:border-border-strong px-3 py-2 rounded-lg text-sm transition-all"
            >
              {showKey ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSave}
            className={`text-sm font-semibold px-4 py-2 rounded-lg transition-all ${
              saved
                ? 'bg-success/15 text-success border border-success/25'
                : 'bg-accent hover:bg-accent-light text-white hover-glow-standard'
            }`}
          >
            {saved ? 'Saved' : 'Save'}
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="text-error hover:bg-error/10 border border-transparent hover:border-error/20 px-4 py-2 rounded-lg text-sm font-medium transition-all"
          >
            Clear
          </button>

          <div className="flex items-center gap-1.5 ml-1">
            <span className={`w-1.5 h-1.5 rounded-full ${hasKey ? 'bg-success' : 'bg-secondary'}`} />
            <span className="text-xs text-secondary font-mono">
              {hasKey ? 'Key set' : 'No key'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Gateway URL Section ───────────────────────────────────────────────────────

function GatewayUrlSection(): React.ReactElement {
  const [url, setUrl] = useState<string>(
    localStorage.getItem('arbiter_gateway_url') ?? 'http://localhost:8000/api/v1',
  )
  const [saved, setSaved] = useState(false)

  const handleSave = (): void => {
    localStorage.setItem('arbiter_gateway_url', url)
    setSaved(true)
    setTimeout(() => {
      setSaved(false)
      window.location.reload()
    }, 1000)
  }

  return (
    <div>
      <SectionHeader title="Gateway URL" subtitle="Base URL of the Arbiter backend API" />
      <div className="max-w-2xl space-y-4">
        <div>
          <label htmlFor="gateway-url-input" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
            Gateway URL
          </label>
          <p className="text-secondary text-xs mb-2.5">
            Defaults to{' '}
            <code className="font-mono text-accent-light bg-accent/8 px-1 rounded">http://localhost:8000/api/v1</code>.
            Saving will reload the page.
          </p>
          <input
            id="gateway-url-input"
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://localhost:8000/api/v1"
            className="w-full bg-base border border-border-strong text-primary text-sm font-mono px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
          />
        </div>

        <button
          type="button"
          onClick={handleSave}
          className="bg-accent hover:bg-accent-light text-white text-sm font-semibold px-4 py-2 rounded-lg transition-all hover-glow-standard"
        >
          {saved ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}

// ── About Section ─────────────────────────────────────────────────────────────

function AboutSection(): React.ReactElement {
  const info: Array<[string, string]> = [
    ['Version', '0.2.0'],
    ['MCP Spec', '2025-03-26'],
    ['License', 'MIT'],
  ]

  return (
    <div>
      <SectionHeader title="About" />
      <div className="max-w-2xl bg-surface border border-border rounded-xl overflow-hidden">
        {info.map(([label, value], idx) => (
          <div
            key={label}
            className={`flex items-center gap-8 px-5 py-3 ${idx < info.length - 1 ? 'border-b border-border' : ''}`}
          >
            <span className="text-muted text-xs font-mono w-24 shrink-0">{label}</span>
            <span className="text-primary text-sm font-mono">{value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Appearance Section ────────────────────────────────────────────────────────

function AppearanceSection(): React.ReactElement {
  const { theme, toggleTheme } = useTheme()

  return (
    <div>
      <SectionHeader title="Appearance" subtitle="Customize the look of the dashboard" />
      <div className="flex items-center justify-between max-w-2xl">
        <div>
          <p className="text-primary text-sm font-medium">Theme</p>
          <p className="text-secondary text-xs mt-0.5">{theme === 'dark' ? 'Dark mode' : 'Light mode'}</p>
        </div>
        <Toggle checked={theme === 'light'} onChange={() => toggleTheme()} />
      </div>
    </div>
  )
}

// ── Cache Section ─────────────────────────────────────────────────────────────

function CacheSection(): React.ReactElement {
  const queryClient = useQueryClient()
  const [flushed, setFlushed] = useState(false)

  const { data: stats, isLoading } = useQuery<CacheStats>({
    queryKey: ['cache-stats'],
    queryFn: () => authClient.get<CacheStats>('/cache/stats').then((r) => r.data),
    refetchInterval: 30_000,
  })

  const flushMutation = useMutation({
    mutationFn: () => authClient.delete('/cache').then(() => undefined),
    onSuccess: () => {
      setFlushed(true)
      void queryClient.invalidateQueries({ queryKey: ['cache-stats'] })
      setTimeout(() => setFlushed(false), 3000)
    },
  })

  return (
    <div>
      <SectionHeader title="Semantic Cache" subtitle="Visibility and control over cached tool call responses" />

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => <div key={i} className="h-4 skeleton-shimmer rounded w-48" />)}
        </div>
      ) : stats ? (
        <div className="space-y-4">
          <div className="flex gap-6 text-sm font-mono">
            <div>
              <p className="text-muted text-xs uppercase tracking-wider mb-1">Active</p>
              <p className="text-primary text-lg font-light">{stats.active_entries.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-muted text-xs uppercase tracking-wider mb-1">Expired</p>
              <p className="text-secondary text-lg font-light">{stats.expired_entries.toLocaleString()}</p>
            </div>
            <div>
              <p className="text-muted text-xs uppercase tracking-wider mb-1">Total</p>
              <p className="text-secondary text-lg font-light">{stats.total_entries.toLocaleString()}</p>
            </div>
          </div>

          {stats.top_tools.length > 0 && (
            <div>
              <p className="text-muted text-xs font-mono uppercase tracking-wider mb-2">Top cached tools</p>
              <div className="space-y-1">
                {stats.top_tools.slice(0, 5).map((t) => (
                  <div key={t.tool_name} className="flex justify-between items-center text-xs font-mono">
                    <span className="text-secondary">{t.tool_name}</span>
                    <span className="text-muted tabular-nums">{t.entries}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="pt-2 border-t border-border">
            <button
              type="button"
              disabled={flushMutation.isPending || stats.active_entries === 0}
              onClick={() => flushMutation.mutate()}
              className="text-error hover:bg-error/10 border border-transparent hover:border-error/20 px-3 py-1.5 rounded-lg text-xs font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {flushMutation.isPending ? 'Flushing…' : flushed ? 'Flushed ✓' : 'Flush Cache'}
            </button>
            <p className="text-muted text-xs mt-1.5">Removes all active cache entries for your org. Cannot be undone.</p>
          </div>
        </div>
      ) : null}
    </div>
  )
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

type Tab = 'general' | 'billing' | 'developer' | 'about'

const TABS: { id: Tab; label: string }[] = [
  { id: 'general',   label: 'General'   },
  { id: 'billing',   label: 'Billing'   },
  { id: 'developer', label: 'Developer' },
  { id: 'about',     label: 'About'     },
]


// ── Page ──────────────────────────────────────────────────────────────────────

function Settings(): React.ReactElement {
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<Tab>(() => {
    const tab = searchParams.get('tab')
    return (tab === 'general' || tab === 'billing' || tab === 'developer' || tab === 'about') ? tab : 'general'
  })

  const handleTabChange = (tab: Tab): void => {
    setActiveTab(tab)
    setSearchParams({ tab }, { replace: true })
  }

  useEffect(() => {
    const tab = searchParams.get('tab')
    if (tab === 'general' || tab === 'billing' || tab === 'developer' || tab === 'about') {
      setActiveTab(tab)
    }
  }, [searchParams])

  return (
    <div className="p-8 animate-fade-in">
      <div className="mb-6">
        <h1 className="font-display text-xl font-semibold tracking-tight text-primary">Settings</h1>
        <p className="text-secondary text-sm mt-1">Configure your Arbiter gateway</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border mb-6 max-w-4xl">
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => handleTabChange(tab.id)}
            className={`px-4 py-2 text-sm font-medium transition-all border-b-2 -mb-px ${
              activeTab === tab.id
                ? 'text-primary border-accent'
                : 'text-secondary border-transparent hover:text-primary hover:border-border-strong'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="max-w-4xl">
        {activeTab === 'general' && (
          <div className="bg-surface border border-border rounded-xl p-6">
            <AppearanceSection />
          </div>
        )}

        {activeTab === 'billing' && (
          <div className="bg-surface border border-border rounded-xl p-6">
            <BillingSection />
          </div>
        )}

        {activeTab === 'developer' && (
          <div className="space-y-4">
            <div className="bg-surface border border-border rounded-xl p-6">
              <ApiKeySection />
            </div>
            <div className="bg-surface border border-border rounded-xl p-6">
              <GatewayUrlSection />
            </div>
            <div className="bg-surface border border-border rounded-xl p-6">
              <CacheSection />
            </div>
          </div>
        )}

        {activeTab === 'about' && (
          <div className="bg-surface border border-border rounded-xl p-6">
            <AboutSection />
          </div>
        )}
      </div>
    </div>
  )
}

export default Settings
