/**
 * NexusAI — Settings page.
 *
 * Sections:
 *   - Profile     (org name, email, role, plan — from GET /auth/me)
 *   - API Key     (agent key stored in localStorage)
 *   - Gateway URL (backend base URL stored in localStorage)
 *   - About       (version, MCP spec, license)
 */

import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { authClient } from '../api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface MeResponse {
  id: string
  email: string
  role: string
  org_id: string
  org_name: string
  org_plan: string
}

// ── Profile Section ───────────────────────────────────────────────────────────

function ProfileSection(): React.ReactElement {
  const { data: me, isLoading, isError } = useQuery<MeResponse>({
    queryKey: ['me'],
    queryFn: () => authClient.get<MeResponse>('/auth/me').then((r) => r.data),
    staleTime: 60_000,
  })

  const rows: Array<{ label: string; value: string }> = me
    ? [
        { label: 'Email', value: me.email },
        { label: 'Role', value: me.role },
        { label: 'Org', value: me.org_name },
        { label: 'Plan', value: me.org_plan },
        { label: 'Org ID', value: me.org_id },
      ]
    : []

  return (
    <div>
      <h2 className="text-secondary text-xs font-semibold uppercase tracking-widest mb-4">
        Profile
      </h2>

      {isLoading && (
        <div className="space-y-2 max-w-xl">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="animate-pulse bg-elevated h-6 rounded" />
          ))}
        </div>
      )}

      {isError && (
        <p className="text-error text-sm font-mono">Failed to load profile.</p>
      )}

      {me && (
        <div className="max-w-xl border border-white/[0.07] divide-y divide-white/[0.07]">
          {rows.map(({ label, value }) => (
            <div
              key={label}
              className="flex items-center gap-6 px-4 py-2.5"
            >
              <span className="text-muted text-xs font-mono w-16 shrink-0">
                {label}
              </span>
              <span
                className={`text-sm font-mono truncate ${
                  label === 'Plan'
                    ? me.org_plan === 'free'
                      ? 'text-secondary'
                      : 'text-green-400'
                    : 'text-primary'
                }`}
              >
                {label === 'Plan' ? value.toUpperCase() : value}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── API Key Section ───────────────────────────────────────────────────────────

function ApiKeySection(): React.ReactElement {
  const [apiKey, setApiKey] = useState<string>(
    localStorage.getItem('nexusai_api_key') ?? '',
  )
  const [showKey, setShowKey] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = (): void => {
    localStorage.setItem('nexusai_api_key', apiKey)
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  const handleClear = (): void => {
    localStorage.removeItem('nexusai_api_key')
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
            Agent API Key
          </label>
          <p className="text-secondary text-xs mb-2">
            Stored locally in your browser. Required to call the proxy gateway as an agent.
            Generate one on the <span className="text-accent-light font-mono">Agents</span> page.
          </p>
          <div className="flex gap-2">
            <input
              id="api-key-input"
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="nxai_..."
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
    localStorage.getItem('nexusai_gateway_url') ?? 'http://localhost:8000/api/v1',
  )
  const [saved, setSaved] = useState(false)

  const handleSave = (): void => {
    localStorage.setItem('nexusai_gateway_url', url)
    setSaved(true)
    setTimeout(() => {
      setSaved(false)
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
            Backend URL
          </label>
          <p className="text-secondary text-xs mb-2">
            Base URL of the NexusAI backend. Defaults to{' '}
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
      <div className="font-mono text-sm max-w-xl border border-white/[0.07] divide-y divide-white/[0.07]">
        {info.map(([label, value]) => (
          <div key={label} className="flex items-center gap-6 px-4 py-2.5">
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
    <div className="p-8 max-w-2xl">
      <h1 className="text-primary text-lg font-semibold mb-8">Settings</h1>

      <ProfileSection />
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
