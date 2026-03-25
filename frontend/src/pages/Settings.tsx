/**
 * NexusAI — Settings page.
 *
 * Sections:
 *   - Gateway API Key (stored in localStorage)
 *   - Gateway URL (base URL for Axios client)
 *   - About (version, MCP spec, license)
 */

import React, { useState } from 'react'

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
            Gateway API Key
          </label>
          <p className="text-secondary text-xs mb-2">
            Stored locally in your browser. Required to authenticate with the NexusAI API.
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
    localStorage.getItem('nexusai_gateway_url') ?? 'http://localhost:8000/api/v1',
  )
  const [saved, setSaved] = useState(false)

  const handleSave = (): void => {
    localStorage.setItem('nexusai_gateway_url', url)
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

      <ApiKeySection />
      <hr className="border-white/[0.07] my-8" />
      <GatewayUrlSection />
      <hr className="border-white/[0.07] my-8" />
      <AboutSection />
    </div>
  )
}

export default Settings
