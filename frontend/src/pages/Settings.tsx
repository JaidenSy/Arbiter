/**
 * Nexvault — Settings page.
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
    <div className="space-y-1">
      <div className="flex justify-between text-xs font-mono text-secondary">
        <span>{label}</span>
        <span
          className={
            isAtLimit
              ? 'text-red-400'
              : isNearLimit
              ? 'text-yellow-400'
              : 'text-primary'
          }
        >
          {used.toLocaleString()} / {limit === null ? '\u221e' : limit.toLocaleString()}
        </span>
      </div>
      {limit !== null && (
        <div className="h-1 bg-elevated rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              isAtLimit
                ? 'bg-red-500'
                : isNearLimit
                ? 'bg-yellow-400'
                : 'bg-accent'
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
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
      <h2 className="text-secondary text-xs font-semibold uppercase tracking-widest mb-4">
        Billing
      </h2>

      {isLoading && (
        <div className="space-y-2 max-w-xl">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="animate-pulse bg-elevated h-6 rounded" />
          ))}
        </div>
      )}

      {isError && (
        <p className="text-error text-sm font-mono">Failed to load billing status.</p>
      )}

      {data && (
        <div className="max-w-xl space-y-4">
          {/* Plan badge */}
          <div className="flex items-center gap-3">
            <span className="text-muted text-xs font-mono">Plan</span>
            <span
              className={`text-xs font-mono font-semibold px-2 py-0.5 rounded uppercase tracking-wider ${
                data.plan === 'enterprise'
                  ? 'bg-violet-500/20 text-violet-300'
                  : data.plan === 'pro'
                  ? 'bg-green-500/20 text-green-300'
                  : 'bg-white/[0.07] text-secondary'
              }`}
            >
              {data.plan}
            </span>
          </div>

          {/* Usage bars — skip for enterprise (unlimited) */}
          {data.plan !== 'enterprise' && (
            <div className="space-y-3 border border-white/[0.07] rounded p-4">
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
              className="bg-accent hover:bg-violet-600 disabled:opacity-60 text-white text-sm font-medium px-4 py-1.5 rounded transition-colors"
            >
              {checkoutMutation.isPending ? 'Redirecting…' : 'Upgrade to Pro'}
            </button>
          )}

          {data.plan === 'pro' && (
            <button
              type="button"
              disabled={portalMutation.isPending}
              onClick={() => portalMutation.mutate()}
              className="bg-elevated hover:bg-white/[0.07] border border-white/[0.14] text-primary text-sm font-medium px-4 py-1.5 rounded transition-colors"
            >
              {portalMutation.isPending ? 'Redirecting…' : 'Manage Subscription'}
            </button>
          )}

          {data.plan === 'enterprise' && (
            <p className="text-secondary text-sm">
              Enterprise plan —{' '}
              <a
                href="mailto:sales@nexvault.dev"
                className="text-accent-light hover:underline"
              >
                contact us
              </a>{' '}
              to manage your subscription.
            </p>
          )}

          {(checkoutMutation.isError || portalMutation.isError) && (
            <p className="text-error text-xs font-mono">
              Billing action failed. Please try again.
            </p>
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
      <h2 className="text-secondary text-xs font-semibold uppercase tracking-widest mb-4">
        API Key
      </h2>
      <div className="max-w-xl space-y-3">
        <div>
          <label
            htmlFor="api-key-input"
            className="block text-primary text-sm font-medium mb-1"
          >
            Gateway API Key
          </label>
          <p className="text-secondary text-xs mb-2">
            Stored locally in your browser. Required to authenticate with the Nexvault API.
          </p>
          <div className="flex gap-2">
            <input
              id="api-key-input"
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="nx_..."
              className="flex-1 bg-elevated border border-white/[0.14] text-primary text-sm font-mono px-3 py-1.5 rounded focus:outline-none focus:border-accent focus:ring-0"
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              className="text-secondary hover:text-primary hover:bg-elevated px-3 py-1.5 rounded text-sm transition-colors border border-white/[0.07]"
            >
              {showKey ? 'Hide' : 'Show'}
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSave}
            className="bg-accent hover:bg-violet-600 text-white text-sm font-medium px-3 py-1.5 rounded transition-colors"
          >
            {saved ? 'Saved' : 'Save'}
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="text-error hover:bg-red-500/10 px-3 py-1.5 rounded text-sm transition-colors"
          >
            Clear
          </button>

          {/* Status indicator */}
          <div className="flex items-center gap-1.5 ml-2">
            <span
              className={`w-1.5 h-1.5 rounded-full ${hasKey ? 'bg-green-400' : 'bg-secondary'}`}
            />
            <span className="text-xs text-secondary font-mono">
              {hasKey ? 'Connected' : 'No key set'}
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
      // Reload so the Axios client picks up the new base URL
      window.location.reload()
    }, 1000)
  }

  return (
    <div>
      <h2 className="text-secondary text-xs font-semibold uppercase tracking-widest mb-4">
        Gateway URL
      </h2>
      <div className="max-w-xl space-y-3">
        <div>
          <label
            htmlFor="gateway-url-input"
            className="block text-primary text-sm font-medium mb-1"
          >
            Gateway URL
          </label>
          <p className="text-secondary text-xs mb-2">
            Base URL of the Nexvault backend. Defaults to{' '}
            <code className="font-mono text-accent-light">http://localhost:8000/api/v1</code>.
            Saving will reload the page to apply the change.
          </p>
          <input
            id="gateway-url-input"
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://localhost:8000/api/v1"
            className="w-full bg-elevated border border-white/[0.14] text-primary text-sm font-mono px-3 py-1.5 rounded focus:outline-none focus:border-accent focus:ring-0"
          />
        </div>

        <button
          type="button"
          onClick={handleSave}
          className="bg-accent hover:bg-violet-600 text-white text-sm font-medium px-3 py-1.5 rounded transition-colors"
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
      <h2 className="text-secondary text-xs font-semibold uppercase tracking-widest mb-4">
        About
      </h2>
      <div className="font-mono text-sm">
        {info.map(([label, value]) => (
          <div
            key={label}
            className="flex gap-8 py-1.5 border-b border-white/[0.07] last:border-0"
          >
            <span className="text-muted w-24 shrink-0">{label}</span>
            <span className="text-primary">{value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

function Settings(): React.ReactElement {
  return (
    <div className="p-8">
      <h1 className="text-primary text-lg font-semibold mb-8">Settings</h1>

      <BillingSection />
      <hr className="border-white/[0.07] my-8" />
      <ApiKeySection />
      <hr className="border-white/[0.07] my-8" />
      <GatewayUrlSection />
      <hr className="border-white/[0.07] my-8" />
      <AboutSection />
    </div>
  )
}

export default Settings
