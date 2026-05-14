/**
 * NexVault — Settings page.
 *
 * Sections:
 *   - Gateway API Key (stored in localStorage)
 *   - Gateway URL (base URL for Axios client)
 *   - About (version, MCP spec, license)
 */

import React, { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { authClient } from '../api/client'
import type { BillingStatus } from '../api/types'

const STRIPE_PRO_PRICE_ID: string = import.meta.env.VITE_STRIPE_PRO_PRICE_ID ?? ''
const SUPPORT_EMAIL: string = import.meta.env.VITE_SUPPORT_EMAIL ?? 'jaidensy07@gmail.com'

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
                : 'bg-gradient-to-r from-accent to-violet-500'
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
  const { data, isLoading, isError } = useQuery<BillingStatus>({
    queryKey: ['billing-status'],
    queryFn: () =>
      authClient.get<BillingStatus>('/billing/status').then((r) => r.data),
    staleTime: 60_000,
  })

  const checkoutMutation = useMutation({
    mutationFn: () =>
      authClient
        .post<{ url: string }>('/billing/checkout', {
          price_id: STRIPE_PRO_PRICE_ID,
        })
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
        <div className="space-y-2 max-w-xl">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="skeleton-shimmer h-6 rounded-lg" />
          ))}
        </div>
      )}

      {isError && (
        <div className="flex items-center gap-2 bg-error/8 border border-error/20 rounded-lg px-3 py-2 max-w-xl">
          <span className="w-1.5 h-1.5 rounded-full bg-error flex-shrink-0" />
          <p className="text-error text-sm">Failed to load billing status.</p>
        </div>
      )}

      {data && (
        <div className="max-w-xl space-y-5">
          {/* Plan badge */}
          <div className="flex items-center gap-3">
            <span className="text-secondary text-xs font-mono">Current plan</span>
            <span
              className={`text-xs font-semibold px-2.5 py-1 rounded-full uppercase tracking-wider ${
                data.plan === 'enterprise'
                  ? 'bg-violet-500/15 text-violet-300 border border-violet-500/25'
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
            <div className="space-y-4 bg-surface border border-white/[0.07] rounded-xl p-5">
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
            <button
              type="button"
              disabled={checkoutMutation.isPending}
              onClick={() => checkoutMutation.mutate()}
              className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 disabled:opacity-60 text-white text-sm font-semibold px-5 py-2 rounded-lg transition-all hover:shadow-[0_0_20px_rgba(124,58,237,0.3)]"
            >
              {checkoutMutation.isPending ? 'Redirecting…' : 'Upgrade to Pro'}
            </button>
          )}

          {data.plan === 'pro' && (
            <button
              type="button"
              disabled={portalMutation.isPending}
              onClick={() => portalMutation.mutate()}
              className="bg-elevated hover:bg-white/[0.07] border border-white/[0.12] hover:border-white/[0.2] text-primary text-sm font-medium px-5 py-2 rounded-lg transition-all"
            >
              {portalMutation.isPending ? 'Redirecting…' : 'Manage Subscription'}
            </button>
          )}

          {data.plan === 'enterprise' && (
            <p className="text-secondary text-sm">
              Enterprise plan —{' '}
              <a
                href={`mailto:${SUPPORT_EMAIL}?subject=NexVault Enterprise Subscription`}
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
    localStorage.getItem('nexvault_api_key') ?? '',
  )
  const [showKey, setShowKey] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = (): void => {
    localStorage.setItem('nexvault_api_key', apiKey)
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  const handleClear = (): void => {
    localStorage.removeItem('nexvault_api_key')
    setApiKey('')
  }

  const hasKey = apiKey.length > 0

  return (
    <div>
      <SectionHeader title="API Key" subtitle="Gateway key stored locally in your browser" />
      <div className="max-w-xl space-y-4">
        <div>
          <label htmlFor="api-key-input" className="block text-xs font-semibold text-secondary mb-1.5 uppercase tracking-widest">
            Gateway API Key
          </label>
          <p className="text-secondary text-xs mb-2.5">
            Required to authenticate agent requests with the NexVault gateway.
          </p>
          <div className="flex gap-2">
            <input
              id="api-key-input"
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="nx_..."
              className="flex-1 bg-elevated border border-white/[0.1] text-primary text-sm font-mono px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              className="text-secondary hover:text-primary bg-elevated hover:bg-white/[0.07] border border-white/[0.1] hover:border-white/[0.18] px-3 py-2 rounded-lg text-sm transition-all"
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
                : 'bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]'
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
    localStorage.getItem('nexvault_gateway_url') ?? 'http://localhost:8000/api/v1',
  )
  const [saved, setSaved] = useState(false)

  const handleSave = (): void => {
    localStorage.setItem('nexvault_gateway_url', url)
    setSaved(true)
    setTimeout(() => {
      setSaved(false)
      window.location.reload()
    }, 1000)
  }

  return (
    <div>
      <SectionHeader title="Gateway URL" subtitle="Base URL of the NexVault backend API" />
      <div className="max-w-xl space-y-4">
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
            className="w-full bg-elevated border border-white/[0.1] text-primary text-sm font-mono px-3 py-2 rounded-lg focus:outline-none focus:border-accent/60 focus:ring-1 focus:ring-accent/30 transition-all"
          />
        </div>

        <button
          type="button"
          onClick={handleSave}
          className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-all hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]"
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
      <div className="max-w-xl bg-surface border border-white/[0.07] rounded-xl overflow-hidden">
        {info.map(([label, value], idx) => (
          <div
            key={label}
            className={`flex items-center gap-8 px-5 py-3 ${idx < info.length - 1 ? 'border-b border-white/[0.05]' : ''}`}
          >
            <span className="text-muted text-xs font-mono w-24 shrink-0">{label}</span>
            <span className="text-primary text-sm font-mono">{value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Settings(): React.ReactElement {
  return (
    <div className="p-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="gradient-text-purple text-xl font-bold">Settings</h1>
        <p className="text-secondary text-sm mt-1">Configure your NexVault gateway</p>
      </div>

      <div className="max-w-2xl space-y-0">
        <div className="bg-surface border border-white/[0.07] rounded-xl p-6 mb-4">
          <BillingSection />
        </div>
        <div className="bg-surface border border-white/[0.07] rounded-xl p-6 mb-4">
          <ApiKeySection />
        </div>
        <div className="bg-surface border border-white/[0.07] rounded-xl p-6 mb-4">
          <GatewayUrlSection />
        </div>
        <div className="bg-surface border border-white/[0.07] rounded-xl p-6">
          <AboutSection />
        </div>
      </div>
    </div>
  )
}

export default Settings
