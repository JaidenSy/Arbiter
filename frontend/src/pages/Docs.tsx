/**
 * Arbiter — In-app documentation page.
 *
 * Route: /docs (public, no ProtectedRoute, no app sidebar)
 * Layout: standalone with left sidebar nav + content area
 */

import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArbiterMark } from '../components/ArbiterLogo'

// ── Navbar ─────────────────────────────────────────────────────────────────────

function Navbar(): React.ReactElement {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-base/80 backdrop-blur-md border-b border-border">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5">
          <ArbiterMark size={28} />
          <span className="text-primary font-semibold text-sm tracking-wide">Arbiter</span>
          <span className="text-muted text-xs ml-1">/ Docs</span>
        </Link>

        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="text-secondary hover:text-primary border border-border hover:border-border-strong px-4 py-1.5 rounded-lg text-sm transition-all"
          >
            Sign In
          </Link>
          <Link
            to="/"
            className="bg-accent hover:bg-accent-light text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition-all hover-glow-standard"
          >
            Dashboard
          </Link>
        </div>
      </div>
    </nav>
  )
}

// ── Sidebar nav ────────────────────────────────────────────────────────────────

const sections = [
  { id: 'quick-start', label: 'Quick Start' },
  { id: 'authentication', label: 'Authentication' },
  { id: 'agents', label: 'Agents' },
  { id: 'permissions', label: 'Permissions' },
  { id: 'vault', label: 'Vault' },
  { id: 'semantic-cache', label: 'Semantic Cache' },
  { id: 'observability', label: 'Observability' },
  { id: 'pricing', label: 'Pricing' },
]

interface DocsSidebarProps {
  activeId: string
  onNav: (id: string) => void
}

function DocsSidebar({ activeId, onNav }: DocsSidebarProps): React.ReactElement {
  return (
    <aside className="hidden lg:block w-56 flex-shrink-0">
      <div className="sticky top-20">
        <p className="text-muted text-xs font-semibold uppercase tracking-widest mb-4 px-3">
          Contents
        </p>
        <nav>
          {sections.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => onNav(s.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all mb-0.5 ${
                activeId === s.id
                  ? 'bg-accent/10 text-accent-light border-l-2 border-accent'
                  : 'text-secondary hover:text-primary hover:bg-white/[0.03] border-l-2 border-transparent'
              }`}
            >
              {s.label}
            </button>
          ))}
        </nav>
      </div>
    </aside>
  )
}

// ── Code block ─────────────────────────────────────────────────────────────────

function Code({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <pre className="bg-elevated rounded-lg p-4 font-mono text-sm text-teal-light overflow-x-auto leading-relaxed whitespace-pre-wrap border border-border">
      {children}
    </pre>
  )
}

function InlineCode({ children }: { children: React.ReactNode }): React.ReactElement {
  return (
    <code className="font-mono text-xs text-accent-light bg-accent/10 px-1.5 py-0.5 rounded border border-accent/15">
      {children}
    </code>
  )
}

// ── Section wrapper ────────────────────────────────────────────────────────────

interface DocSectionProps {
  id: string
  title: string
  children: React.ReactNode
}

function DocSection({ id, title, children }: DocSectionProps): React.ReactElement {
  return (
    <section id={id} className="mb-16 scroll-mt-20">
      <h2 className="font-display text-xl font-semibold tracking-tight text-primary mb-6">{title}</h2>
      <div className="space-y-4">{children}</div>
    </section>
  )
}

// ── Endpoint row ───────────────────────────────────────────────────────────────

interface EndpointProps {
  method: string
  path: string
  description: string
}

function Endpoint({ method, path, description }: EndpointProps): React.ReactElement {
  const methodColors: Record<string, string> = {
    GET: 'text-success bg-success/10 border-success/20',
    POST: 'text-accent-light bg-accent/10 border-accent/20',
    DELETE: 'text-error bg-error/10 border-error/20',
  }
  const color = methodColors[method] ?? 'text-secondary bg-elevated border-border'

  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-0">
      <span
        className={`inline-block px-2 py-0.5 rounded text-xs font-mono font-semibold border flex-shrink-0 mt-0.5 ${color}`}
      >
        {method}
      </span>
      <div>
        <span className="font-mono text-sm text-primary">{path}</span>
        <p className="text-secondary text-xs mt-0.5">{description}</p>
      </div>
    </div>
  )
}

// ── Content ────────────────────────────────────────────────────────────────────

function DocsContent(): React.ReactElement {
  return (
    <div>
      {/* Quick Start */}
      <DocSection id="quick-start" title="Quick Start">
        <p className="text-secondary text-sm leading-relaxed">
          Get your first agent connected to Arbiter in under 5 minutes.
        </p>
        <ol className="space-y-3">
          {[
            'Register at arbiter.app. Free plan, no credit card required.',
            'Create your first agent in the dashboard and copy the API key.',
            'Set your MCP client base URL to your Arbiter gateway URL.',
            'Make your first tool call. Traffic is proxied, cached, and logged automatically.',
          ].map((step, i) => (
            <li key={i} className="flex items-start gap-3 text-sm text-secondary">
              <span className="w-5 h-5 rounded-full bg-accent/15 border border-accent/25 flex items-center justify-center text-accent-light text-xs font-mono flex-shrink-0 mt-0.5">
                {i + 1}
              </span>
              {step}
            </li>
          ))}
        </ol>
        <Code>{`# Example: connect Claude Desktop to Arbiter
{
  "mcpServers": {
    "arbiter": {
      "url": "https://your-arbiter.railway.app/mcp",
      "headers": {
        "Authorization": "Bearer nxai_your_agent_key_here"
      }
    }
  }
}`}</Code>
      </DocSection>

      {/* Authentication */}
      <DocSection id="authentication" title="Authentication">
        <p className="text-secondary text-sm leading-relaxed">
          Arbiter uses two authentication mechanisms depending on context.
        </p>

        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-primary font-semibold text-sm mb-3">Agent API calls</h3>
          <p className="text-secondary text-xs mb-3">
            All agent tool calls use a Bearer token in the <InlineCode>Authorization</InlineCode> header.
            Each agent has a unique key. Don't share keys between agents.
          </p>
          <Code>Authorization: Bearer nxai_{'<your-agent-key>'}</Code>
        </div>

        <div className="bg-surface border border-border rounded-xl p-5">
          <h3 className="text-primary font-semibold text-sm mb-3">User JWT (dashboard)</h3>
          <p className="text-secondary text-xs mb-3">
            Dashboard API calls use a JWT obtained via the login endpoint.
            The JWT is automatically managed by the frontend.
          </p>
          <Code>{`POST /api/v1/auth/login
{ "email": "you@example.com", "password": "..." }
→ { "access_token": "eyJ..." }`}</Code>
        </div>
      </DocSection>

      {/* Agents */}
      <DocSection id="agents" title="Agents">
        <p className="text-secondary text-sm leading-relaxed">
          Every AI agent that calls tools through Arbiter must first be registered.
          Registration gives the agent a unique cryptographic API key.
        </p>

        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <Endpoint method="POST" path="/api/v1/agents" description="Register a new agent. Returns an api_key (shown once — store it immediately)." />
          <Endpoint method="GET" path="/api/v1/agents" description="List all agents for the authenticated user." />
          <Endpoint method="DELETE" path="/api/v1/agents/:id" description="Deactivate an agent. All its permissions are revoked." />
        </div>

        <Code>{`# Register agent
POST /api/v1/agents
{
  "name": "my-research-agent",
  "description": "Reads files and calls web APIs"
}

# Response
{
  "id": "agt_abc123",
  "api_key": "nxai_xyz...",   ← shown once
  "is_active": true
}`}</Code>
      </DocSection>

      {/* Permissions */}
      <DocSection id="permissions" title="Permissions">
        <p className="text-secondary text-sm leading-relaxed">
          Tool-level permissions control exactly which tools an agent is allowed to invoke.
          Use <InlineCode>*</InlineCode> to grant all tools on an MCP server.
        </p>

        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <Endpoint method="POST" path="/api/v1/tool-permissions" description="Grant a specific tool (or *) to an agent." />
          <Endpoint method="DELETE" path="/api/v1/tool-permissions/:id" description="Revoke a tool permission immediately." />
        </div>

        <Code>{`# Grant read_file to an agent
POST /api/v1/tool-permissions
{
  "agent_id": "agt_abc123",
  "mcp_server_id": "srv_xyz",
  "tool_name": "read_file"
}

# Grant all tools
{ "tool_name": "*" }`}</Code>
      </DocSection>

      {/* Vault */}
      <DocSection id="vault" title="Vault">
        <p className="text-secondary text-sm leading-relaxed">
          The vault stores secrets per agent using AES-256-GCM encryption.
          Secrets are injected into tool calls at call time. They never leave the vault unencrypted.
        </p>

        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <Endpoint method="POST" path="/api/v1/vault" description="Store a secret. The value is encrypted immediately on write." />
          <Endpoint method="GET" path="/api/v1/vault" description="List secrets. Names only; values are never returned." />
          <Endpoint method="GET" path="/api/v1/vault/:name" description="Retrieve and decrypt a specific secret value." />
        </div>

        <Code>{`# Store a secret
POST /api/v1/vault
{
  "agent_id": "agt_abc123",
  "name": "GITHUB_TOKEN",
  "value": "ghp_..."
}

# In tool call payloads, reference secrets like:
{ "headers": { "Authorization": "Bearer {{GITHUB_TOKEN}}" } }`}</Code>
      </DocSection>

      {/* Semantic Cache */}
      <DocSection id="semantic-cache" title="Semantic Cache">
        <p className="text-secondary text-sm leading-relaxed">
          Arbiter automatically caches tool call responses. Identical calls return instantly
          without hitting the upstream MCP server, reducing latency and API costs.
        </p>

        <div className="bg-surface border border-border rounded-xl p-5 space-y-3">
          {[
            { label: 'Cache TTL', value: '1 hour (default)' },
            { label: 'Cache key', value: 'agent_id + tool_name + arguments hash' },
            { label: 'Cache hit indicator', value: 'Shown in session trace as cached: true' },
            { label: 'Configuration', value: 'Automatic. No setup required.' },
          ].map((row) => (
            <div key={row.label} className="flex items-center justify-between text-sm border-b border-border last:border-0 pb-3 last:pb-0">
              <span className="text-secondary">{row.label}</span>
              <span className="font-mono text-xs text-accent-light">{row.value}</span>
            </div>
          ))}
        </div>
      </DocSection>

      {/* Observability */}
      <DocSection id="observability" title="Observability">
        <p className="text-secondary text-sm leading-relaxed">
          Every tool call is logged in a session trace. Sessions group related tool calls
          by agent and time window. Full request/response payloads are stored and queryable.
        </p>

        <div className="bg-surface border border-border rounded-xl overflow-hidden">
          <Endpoint method="GET" path="/api/v1/sessions" description="List all sessions. Filter by agent_id or date range." />
          <Endpoint method="GET" path="/api/v1/sessions/:id" description="Get full session trace with all tool call events." />
        </div>

        <Code>{`# Session trace structure
{
  "session_id": "ses_abc",
  "agent_id": "agt_xyz",
  "events": [
    {
      "tool": "read_file",
      "cached": false,
      "duration_ms": 84,
      "status": "success",
      "timestamp": "2026-05-14T10:23:01Z"
    }
  ]
}`}</Code>
      </DocSection>

      {/* Pricing */}
      <DocSection id="pricing" title="Pricing">
        <p className="text-secondary text-sm leading-relaxed">
          Arbiter offers a free tier with generous limits for personal projects and evaluation.
          See the full plan comparison on the landing page.
        </p>
        <div>
          <Link
            to="/#pricing"
            className="inline-flex items-center gap-2 text-accent-light hover:text-primary text-sm font-medium transition-colors group"
          >
            View pricing plans →
          </Link>
        </div>
      </DocSection>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

function Docs(): React.ReactElement {
  const [activeId, setActiveId] = useState('quick-start')

  // Sync active section on scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id)
          }
        }
      },
      { rootMargin: '-20% 0px -60% 0px', threshold: 0 },
    )

    sections.forEach((s) => {
      const el = document.getElementById(s.id)
      if (el) observer.observe(el)
    })

    return () => observer.disconnect()
  }, [])

  const handleNav = (id: string): void => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setActiveId(id)
    }
  }

  return (
    <div className="min-h-screen bg-base text-primary">
      <Navbar />

      <div className="pt-14 max-w-7xl mx-auto px-6 flex gap-10 py-12">
        <DocsSidebar activeId={activeId} onNav={handleNav} />

        <main className="flex-1 min-w-0 animate-fade-in">
          <div className="mb-12">
            <h1 className="font-display text-2xl font-semibold tracking-tight text-primary mb-2">Documentation</h1>
            <p className="text-secondary text-sm">
              Everything you need to integrate Arbiter with your AI agents.
            </p>
          </div>
          <DocsContent />
        </main>
      </div>
    </div>
  )
}

export default Docs
