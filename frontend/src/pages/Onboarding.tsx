/**
 * Arbiter — Onboarding wizard.
 *
 * Route: /onboarding (protected, no sidebar)
 * 4-step wizard that walks a new user through:
 *   Step 1 — Welcome
 *   Step 2 — Register first agent (returns one-time API key)
 *   Step 3 — Add first MCP server
 *   Step 4 — Done + curl snippet
 */

import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { authClient } from '../api/client'
import { useAuth } from '../context/AuthContext'
import CopyButton from '../components/CopyButton'
import type { AgentCreateResponse, MCPServer } from '../api/types'

// ── Progress indicator ────────────────────────────────────────────────────────

interface ProgressDotsProps {
  total: number
  current: number // 0-indexed
}

function ProgressDots({ total, current }: ProgressDotsProps): React.ReactElement {
  return (
    <div className="flex items-center gap-2 justify-center mb-12">
      {Array.from({ length: total }).map((_, i) => {
        const isDone = i < current
        const isActive = i === current
        return (
          <div
            key={i}
            className={`w-2 h-2 rounded-full transition-colors ${
              isDone
                ? 'bg-green-400'
                : isActive
                ? 'bg-accent'
                : 'bg-white/20'
            }`}
          />
        )
      })}
    </div>
  )
}

// ── Step 1 — Welcome ──────────────────────────────────────────────────────────

interface Step1Props {
  orgName: string
  onNext: () => void
}

function Step1({ orgName, onNext }: Step1Props): React.ReactElement {
  return (
    <div className="text-center space-y-6">
      <h1 className="text-white text-2xl font-mono font-semibold">
        Welcome to Arbiter, {orgName}
      </h1>
      <p className="text-secondary text-sm font-mono leading-relaxed max-w-sm mx-auto">
        Arbiter is a developer-first MCP gateway that gives your agents identity,
        tool-level access control, a secrets vault, and full observability — all in one place.
      </p>
      <p className="text-secondary text-sm font-mono leading-relaxed max-w-sm mx-auto">
        Let's get you set up in under 2 minutes.
      </p>
      <button
        onClick={onNext}
        className="bg-accent hover:bg-violet-600 text-white font-mono text-sm px-6 py-2 rounded transition-colors"
      >
        Get started →
      </button>
    </div>
  )
}

// ── Step 2 — Register first agent ─────────────────────────────────────────────

interface Step2Props {
  onNext: (agentName: string, apiKey: string) => void
}

const createAgent = (payload: {
  name: string
  description: string
}): Promise<AgentCreateResponse> =>
  authClient.post<AgentCreateResponse>('/agents', payload).then((r) => r.data)

function Step2({ onNext }: Step2Props): React.ReactElement {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [createdName, setCreatedName] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: createAgent,
    onSuccess: (data) => {
      setCreatedKey(data.api_key)
      setCreatedName(data.name)
      setError(null)
    },
    onError: () => {
      setError('Failed to register agent. Please try again.')
    },
  })

  const handleCreate = (e: React.FormEvent): void => {
    e.preventDefault()
    if (!name.trim()) return
    mutation.mutate({ name: name.trim(), description: description.trim() })
  }

  return (
    <div className="space-y-6 max-w-md w-full mx-auto">
      <div>
        <h2 className="text-white text-lg font-mono font-semibold mb-1">Register your first agent</h2>
        <p className="text-secondary text-xs font-mono">Each agent gets a unique API key used to authenticate tool calls.</p>
      </div>

      {!createdKey ? (
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label htmlFor="agent-name" className="block text-xs text-secondary mb-1 uppercase tracking-wider">
              Agent Name <span className="text-red-400">*</span>
            </label>
            <input
              id="agent-name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. my-agent"
              className="w-full bg-elevated border border-white/10 text-white font-mono text-sm px-3 py-2 rounded focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
            />
          </div>

          <div>
            <label htmlFor="agent-desc" className="block text-xs text-secondary mb-1 uppercase tracking-wider">
              Description
            </label>
            <input
              id="agent-desc"
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional"
              className="w-full bg-elevated border border-white/10 text-white font-mono text-sm px-3 py-2 rounded focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
            />
          </div>

          {error && <p className="text-red-400 text-xs font-mono">{error}</p>}

          <button
            type="submit"
            disabled={mutation.isPending || !name.trim()}
            className="bg-accent hover:bg-violet-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-mono text-sm px-4 py-2 rounded transition-colors"
          >
            {mutation.isPending ? 'Registering…' : 'Register agent'}
          </button>
        </form>
      ) : (
        <div className="space-y-4">
          <div className="bg-yellow-950/40 border border-yellow-800/50 rounded p-3">
            <p className="text-yellow-400 text-xs font-mono font-semibold">
              This key is shown once. Copy it now — you won't be able to retrieve it later.
            </p>
          </div>

          <div>
            <p className="text-xs text-secondary mb-2 font-mono uppercase tracking-wider">API Key</p>
            <div className="bg-base border border-white/10 rounded p-3 flex items-start gap-2">
              <code className="text-xs font-mono text-accent-light flex-1 break-all">
                {createdKey}
              </code>
              <CopyButton text={createdKey} />
            </div>
          </div>

          <button
            onClick={() => onNext(createdName, createdKey)}
            className="bg-accent hover:bg-violet-600 text-white font-mono text-sm px-4 py-2 rounded transition-colors"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}

// ── Step 3 — Add MCP server ───────────────────────────────────────────────────

interface Step3Props {
  onNext: (serverName: string) => void
}

const createServer = (payload: {
  name: string
  base_url: string
  cache_enabled: boolean
}): Promise<MCPServer> =>
  authClient.post<MCPServer>('/mcp-servers', payload).then((r) => r.data)

function Step3({ onNext }: Step3Props): React.ReactElement {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [cacheEnabled, setCacheEnabled] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: createServer,
    onSuccess: (data) => {
      onNext(data.name)
    },
    onError: () => {
      setError('Failed to add MCP server. Please try again.')
    },
  })

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault()
    if (!name.trim() || !url.trim()) return
    mutation.mutate({ name: name.trim(), base_url: url.trim(), cache_enabled: cacheEnabled })
  }

  return (
    <div className="space-y-6 max-w-md w-full mx-auto">
      <div>
        <h2 className="text-white text-lg font-mono font-semibold mb-1">Add your first MCP server</h2>
        <p className="text-secondary text-xs font-mono">MCP servers expose tools your agents can call through the gateway.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="server-name" className="block text-xs text-secondary mb-1 uppercase tracking-wider">
            Server Name <span className="text-red-400">*</span>
          </label>
          <input
            id="server-name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. filesystem"
            className="w-full bg-elevated border border-white/10 text-white font-mono text-sm px-3 py-2 rounded focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
          />
        </div>

        <div>
          <label htmlFor="server-url" className="block text-xs text-secondary mb-1 uppercase tracking-wider">
            Server URL <span className="text-red-400">*</span>
          </label>
          <input
            id="server-url"
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="http://localhost:8001"
            className="w-full bg-elevated border border-white/10 text-white font-mono text-sm px-3 py-2 rounded focus:outline-none focus:ring-1 focus:ring-accent focus:border-accent transition-colors"
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            role="switch"
            aria-checked={cacheEnabled}
            onClick={() => setCacheEnabled(!cacheEnabled)}
            className={`relative w-9 h-5 rounded-full transition-colors ${cacheEnabled ? 'bg-accent' : 'bg-elevated border border-white/10'}`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${cacheEnabled ? 'translate-x-4' : ''}`}
            />
          </button>
          <span className="text-xs text-secondary font-mono">Enable semantic caching</span>
        </div>

        {error && <p className="text-red-400 text-xs font-mono">{error}</p>}

        <button
          type="submit"
          disabled={mutation.isPending || !name.trim() || !url.trim()}
          className="bg-accent hover:bg-violet-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-mono text-sm px-4 py-2 rounded transition-colors"
        >
          {mutation.isPending ? 'Adding…' : 'Add server'}
        </button>
      </form>
    </div>
  )
}

// ── Step 4 — Done ─────────────────────────────────────────────────────────────

interface Step4Props {
  agentName: string
  agentApiKey: string
  serverName: string
  onFinish: () => void
}

function Step4({ agentName, agentApiKey, serverName, onFinish }: Step4Props): React.ReactElement {
  const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'
  const curlSnippet = `curl -X POST ${baseUrl}/proxy/tool-call \\
  -H "Authorization: Bearer ${agentApiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "server_name": "${serverName}",
    "tool_name": "your_tool_name",
    "params": {}
  }'`

  return (
    <div className="space-y-6 max-w-lg w-full mx-auto">
      <div className="text-center">
        <div className="text-green-400 text-4xl mb-3">✓</div>
        <h2 className="text-white text-lg font-mono font-semibold mb-1">You're all set</h2>
        <p className="text-secondary text-xs font-mono">Here's a summary of what was created.</p>
      </div>

      <div className="space-y-2 text-sm font-mono">
        <div className="flex justify-between border-b border-white/[0.07] py-2">
          <span className="text-secondary">Agent</span>
          <span className="text-white">{agentName}</span>
        </div>
        <div className="flex justify-between border-b border-white/[0.07] py-2">
          <span className="text-secondary">MCP Server</span>
          <span className="text-white">{serverName}</span>
        </div>
      </div>

      <div>
        <p className="text-xs text-secondary mb-2 font-mono uppercase tracking-wider">Make your first tool call</p>
        <div className="bg-base border border-white/10 rounded p-3 flex items-start gap-2">
          <pre className="text-xs font-mono text-accent-light flex-1 overflow-x-auto whitespace-pre-wrap break-all">
            {curlSnippet}
          </pre>
          <CopyButton text={curlSnippet} />
        </div>
      </div>

      <button
        onClick={onFinish}
        className="w-full bg-accent hover:bg-violet-600 text-white font-mono text-sm py-2 rounded transition-colors"
      >
        Go to Dashboard →
      </button>
    </div>
  )
}

// ── Onboarding page ───────────────────────────────────────────────────────────

function Onboarding(): React.ReactElement {
  const { user } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [step, setStep] = useState(0) // 0-indexed
  const [agentName, setAgentName] = useState('')
  const [agentApiKey, setAgentApiKey] = useState('')
  const [serverName, setServerName] = useState('')

  const syncStatus = async (): Promise<void> => {
    try {
      await authClient.get('/onboarding/status')
    } catch {
      // Non-blocking — endpoint may not exist yet
    }
  }

  const handleStep1Next = (): void => {
    void syncStatus()
    setStep(1)
  }

  const handleStep2Next = (name: string, key: string): void => {
    setAgentName(name)
    setAgentApiKey(key)
    localStorage.setItem('arbiter_api_key', key)
    void syncStatus()
    setStep(2)
  }

  const handleStep3Next = (name: string): void => {
    setServerName(name)
    void syncStatus()
    setStep(3)
  }

  const handleFinish = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['stats'] })
    navigate('/')
  }

  const orgName = user?.org_name ?? 'your organization'

  return (
    <div className="min-h-screen bg-base flex flex-col items-center justify-center font-mono px-4 py-12">
      <ProgressDots total={4} current={step} />

      {step === 0 && <Step1 orgName={orgName} onNext={handleStep1Next} />}
      {step === 1 && <Step2 onNext={handleStep2Next} />}
      {step === 2 && <Step3 onNext={handleStep3Next} />}
      {step === 3 && (
        <Step4
          agentName={agentName}
          agentApiKey={agentApiKey}
          serverName={serverName}
          onFinish={handleFinish}
        />
      )}
    </div>
  )
}

export default Onboarding
