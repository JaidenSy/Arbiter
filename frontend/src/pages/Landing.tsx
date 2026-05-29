/**
 * Arbiter — Marketing landing page.
 *
 * Shown to unauthenticated users at /.
 * No sidebar. Standalone dark layout.
 */

import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Check } from 'lucide-react'
import { ArbiterMark } from '../components/ArbiterLogo'
import { useAuth } from '../context/AuthContext'
import AuthModal, { type AuthMode } from '../components/AuthModal'
import HeroBackground from '../components/HeroBackground'

const SUPPORT_EMAIL: string =
  (import.meta.env.VITE_SUPPORT_EMAIL as string | undefined) ?? 'support@arbiterai.dev'

// ── Navbar ─────────────────────────────────────────────────────────────────────

interface NavbarProps { onSignIn: () => void; onGetStarted: () => void }

function Navbar({ onSignIn, onGetStarted }: NavbarProps): React.ReactElement {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-base/85 backdrop-blur-md border-b border-border">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <ArbiterMark size={26} />
          <span className="font-display text-primary font-semibold text-sm tracking-tight">Arbiter</span>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onSignIn}
            className="press text-secondary hover:text-primary border border-border-strong hover:border-border-strong px-4 py-1.5 rounded-lg text-sm transition-colors duration-150 ease-[var(--ease-out-expo)]"
          >
            Sign In
          </button>
          <button
            onClick={onGetStarted}
            className="press bg-accent hover:bg-accent-light text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition-colors duration-150 ease-[var(--ease-out-expo)]"
          >
            Get Started Free
          </button>
        </div>
      </div>
    </nav>
  )
}

// ── Hero ───────────────────────────────────────────────────────────────────────

interface HeroProps { onGetStarted: () => void; onSignIn: () => void }

function Hero({ onGetStarted, onSignIn }: HeroProps): React.ReactElement {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center text-center px-6 overflow-hidden">
      <HeroBackground />

      <div
        className="absolute bottom-0 left-0 right-0 h-52 pointer-events-none"
        style={{ background: 'linear-gradient(to bottom, transparent, var(--color-base))' }}
        aria-hidden
      />

      <div className="relative max-w-3xl mx-auto pt-28 sm:pt-24 lg:pt-20">
        <p className="kicker mb-5" style={{ animationDelay: '0ms' }}>
          MCP Security Gateway
        </p>

        <h1
          className="hero-display text-primary mb-6 animate-fade-in"
          style={{ animationDelay: '60ms', animationFillMode: 'both' }}
        >
          Your AI agents are running
          <br />
          <span className="text-secondary">without guardrails.</span>
        </h1>

        <p
          className="text-secondary text-base sm:text-lg max-w-2xl mx-auto mb-10 animate-fade-in"
          style={{ animationDelay: '120ms', animationFillMode: 'both' }}
        >
          Shared credentials, no audit trail, agents that can call any tool they want.
          Arbiter sits between your agents and your MCP servers. Every call goes through it:
          logged, cached, and gated by the permissions you set.
        </p>

        <div
          className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-6 animate-fade-in"
          style={{ animationDelay: '200ms', animationFillMode: 'both' }}
        >
          <button
            onClick={onGetStarted}
            className="press bg-accent hover:bg-accent-light text-white font-semibold px-6 py-3 rounded-xl transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover-glow-standard text-sm"
          >
            Start for Free
          </button>
          <button
            onClick={onSignIn}
            className="press text-secondary hover:text-primary border border-border-strong hover:border-border-strong px-6 py-3 rounded-xl text-sm transition-colors duration-150 ease-[var(--ease-out-expo)]"
          >
            Sign In
          </button>
        </div>

        <p
          className="text-muted text-xs animate-fade-in"
          style={{ animationDelay: '200ms', animationFillMode: 'both' }}
        >
          Free plan includes 2 agents · 5,000 tool calls/mo · No credit card required
        </p>

        {/* Terminal demo */}
        <div
          className="mt-14 bg-surface/85 backdrop-blur-sm border border-border-strong rounded-lg p-5 text-left max-w-xl mx-auto shadow-2xl animate-fade-in overflow-hidden"
          style={{ animationDelay: '280ms', animationFillMode: 'both' }}
        >
          <div className="flex items-center gap-1.5 mb-4">
            <span className="w-2.5 h-2.5 rounded-full bg-error/70" />
            <span className="w-2.5 h-2.5 rounded-full bg-warning/70" />
            <span className="w-2.5 h-2.5 rounded-full bg-success/70" />
          </div>
          <pre className="font-mono text-xs text-secondary leading-relaxed overflow-x-auto">
            <span className="text-muted">$</span>{' '}
            <span className="text-teal-light">curl</span>{' '}
            <span className="text-primary">-X POST https://api.arbiterai.dev/api/v1/proxy/tool-call \</span>
            {'\n'}
            {'  '}<span className="text-accent-light">-H</span>{' '}
            <span className="text-success">"Authorization: Bearer nxai_abc123..."</span>
            {'\n'}
            {'  '}<span className="text-accent-light">-d</span>{' '}
            <span className="text-success">'{`{"server_name":"filesystem","tool_name":"read_file","params":{"path":"/app/config.json"}}`}'</span>
            {'\n\n'}
            <span className="text-muted"># Response</span>
            {'\n'}
            <span className="text-teal-light">{'{'}</span>
            {'\n'}
            {'  '}<span className="text-accent-light">"cached"</span>
            <span className="text-primary">: </span>
            <span className="text-warning">false</span>
            <span className="text-primary">,</span>
            {'\n'}
            {'  '}<span className="text-accent-light">"agent_id"</span>
            <span className="text-primary">: </span>
            <span className="text-success">"agt_xyz789"</span>
            <span className="text-primary">,</span>
            {'\n'}
            {'  '}<span className="text-accent-light">"result"</span>
            <span className="text-primary">: {'{'}</span>
            <span className="text-muted">...</span>
            <span className="text-primary">{'}'}</span>
            {'\n'}
            <span className="text-teal-light">{'}'}</span>
          </pre>
        </div>
      </div>
    </section>
  )
}

// ── Product Proof ──────────────────────────────────────────────────────────────

const mockRows = [
  { agent: 'claude-local', tool: 'read_file',       arg: '/app/config.json',              cached: true,  ms: 2,   ok: true  },
  { agent: 'claude-local', tool: 'search_web',      arg: '"MCP security best practices"', cached: false, ms: 312, ok: true  },
  { agent: 'writer-bot',   tool: 'write_file',      arg: '/reports/q2.md',                cached: false, ms: 89,  ok: true  },
  { agent: 'scraper-v2',   tool: 'delete_database', arg: '*',                             cached: false, ms: 4,   ok: false },
]

function ProductProof(): React.ReactElement {
  return (
    <section className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="mb-14">
          <p className="text-muted text-xs font-semibold uppercase tracking-widest mb-3">What you actually get</p>
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary max-w-xl">
            Full visibility into every tool call your agents make
          </h2>
        </div>

        {/* Mock session trace */}
        <div className="bg-surface border border-border rounded-2xl overflow-hidden mb-8">
          <div className="border-b border-border px-5 py-3.5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="text-primary text-sm font-medium">Session trace</span>
              <span className="bg-elevated text-muted text-[10px] font-semibold px-2 py-0.5 rounded-full border border-border tracking-wide">SAMPLE</span>
            </div>
            <span className="text-muted text-xs font-mono">org / 4 events</span>
          </div>

          <div className="divide-y divide-border">
            {mockRows.map((row, i) => (
              <div
                key={i}
                className={`flex items-center gap-4 px-5 py-3.5 text-xs font-mono ${row.ok ? '' : 'bg-error/[0.04]'}`}
              >
                <span className={`font-semibold w-8 flex-shrink-0 ${row.ok ? 'text-success' : 'text-error'}`}>
                  {row.ok ? '200' : '403'}
                </span>
                <span className="text-muted w-24 flex-shrink-0 truncate">{row.agent}</span>
                <span className="text-accent-light w-36 flex-shrink-0 truncate">{row.tool}</span>
                <span className="text-muted flex-1 truncate hidden sm:block">{row.arg}</span>
                <span className={`flex-shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded border ${
                  row.cached
                    ? 'text-teal-light bg-teal/10 border-teal/20'
                    : row.ok
                    ? 'text-muted border-border'
                    : 'text-error/70 border-error/20'
                }`}>
                  {row.cached ? 'HIT' : row.ok ? 'MISS' : 'BLOCKED'}
                </span>
                <span className="text-muted flex-shrink-0 w-12 text-right">{row.ms}ms</span>
              </div>
            ))}
          </div>

          <div className="border-t border-border px-5 py-3 flex items-center gap-6 text-xs text-muted">
            <span>3 allowed · 1 blocked</span>
            <span>1 cache hit</span>
            <span className="ml-auto font-mono">2026-05-29 · 10:23 UTC</span>
          </div>
        </div>

        {/* Three concrete proof points */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <div className="bg-surface border border-border rounded-xl p-5">
            <p className="text-primary font-semibold text-sm mb-2">One key per agent</p>
            <p className="text-secondary text-sm mb-4">Each agent gets its own cryptographic key. Revoke or rotate one without touching the others.</p>
            <code className="text-[11px] font-mono text-accent-light bg-accent/8 border border-accent/15 rounded px-3 py-2 block">
              nxai_a7f3k9xm...
            </code>
          </div>
          <div className="bg-surface border border-border rounded-xl p-5">
            <p className="text-primary font-semibold text-sm mb-2">Blocked at the gateway</p>
            <p className="text-secondary text-sm mb-4">If an agent tries a tool it was not granted, it gets a 403. Not a silent pass-through.</p>
            <code className="text-[11px] font-mono text-error bg-error/8 border border-error/15 rounded px-3 py-2 block">
              403 · tool not permitted
            </code>
          </div>
          <div className="bg-surface border border-border rounded-xl p-5">
            <p className="text-primary font-semibold text-sm mb-2">Secrets stay in the vault</p>
            <p className="text-secondary text-sm mb-4">Reference secrets by name in tool params. The value is decrypted and injected at call time.</p>
            <code className="text-[11px] font-mono text-warning bg-warning/8 border border-warning/15 rounded px-3 py-2 block">
              {`{ "token": "{{GITHUB_TOKEN}}" }`}
            </code>
          </div>
        </div>
      </div>
    </section>
  )
}

// ── Comparison ─────────────────────────────────────────────────────────────────

function Comparison(): React.ReactElement {
  const check = (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-success mx-auto">
      <polyline points="20 6 9 17 4 12"/>
    </svg>
  )
  const cross = (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-muted mx-auto">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  )

  type CellVal = boolean | 'partial' | string

  const rows: { feature: string; arbiter: CellVal; litellm: CellVal; portkey: CellVal; diy: CellVal; enterpriseOnly?: boolean }[] = [
    { feature: 'Per-agent identity',          arbiter: true,      litellm: false,     portkey: false,     diy: '~3 months' },
    { feature: 'Tool-level RBAC',             arbiter: true,      litellm: false,     portkey: false,     diy: '~2 months' },
    { feature: 'Encrypted secrets vault',     arbiter: true,      litellm: false,     portkey: false,     diy: '~2 months' },
    { feature: 'Semantic cache (pgvector)',   arbiter: true,      litellm: 'partial', portkey: 'partial', diy: '~3 months' },
    { feature: 'Full request/response audit', arbiter: true,      litellm: 'partial', portkey: true,      diy: '~1 month'  },
    { feature: 'MCP protocol native',         arbiter: true,      litellm: false,     portkey: false,     diy: 'depends'   },
    { feature: 'Self-hosted',                 arbiter: true,      litellm: true,      portkey: false,     diy: true,        enterpriseOnly: true },
  ]

  function renderCell(val: CellVal): React.ReactNode {
    if (val === true) return check
    if (val === false) return cross
    if (val === 'partial') return <span className="text-warning text-xs font-medium">Partial</span>
    return <span className="text-muted text-xs">{val}</span>
  }

  return (
    <section className="py-24 px-6 bg-surface/30">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary mb-6">How Arbiter compares</h2>
          <p className="text-secondary text-base max-w-xl mx-auto">
            LiteLLM and Portkey solve LLM routing. Arbiter solves MCP security.
          </p>
        </div>

        <div className="overflow-x-auto border border-border rounded-xl">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border-strong">
                <th className="text-left py-3 pl-5 pr-6 text-secondary font-normal w-[45%]" />
                <th className="py-3 px-4 text-center">
                  <span className="text-accent-light font-semibold">Arbiter</span>
                </th>
                <th className="py-3 px-4 text-center text-secondary font-medium">LiteLLM</th>
                <th className="py-3 px-4 text-center text-secondary font-medium">Portkey</th>
                <th className="py-3 px-4 text-center text-secondary font-medium">DIY</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={row.feature} className={`border-b border-border ${i % 2 === 0 ? 'bg-white/[0.015]' : ''}`}>
                  <td className="py-3.5 pl-5 pr-6 text-secondary">
                    <span className="inline-flex items-center gap-2 flex-wrap">
                      {row.feature}
                      {row.enterpriseOnly && (
                        <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded border border-border-accent text-accent-light bg-accent/10 leading-none whitespace-nowrap">
                          Enterprise
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-center">{renderCell(row.arbiter)}</td>
                  <td className="py-3.5 px-4 text-center">{renderCell(row.litellm)}</td>
                  <td className="py-3.5 px-4 text-center">{renderCell(row.portkey)}</td>
                  <td className="py-3.5 px-4 text-center">{renderCell(row.diy)}</td>
                </tr>
              ))}
              <tr className="border-t border-border-accent bg-accent/[0.05]">
                <td className="py-3.5 pl-5 pr-6 text-primary font-semibold">Cost</td>
                <td className="py-3.5 px-4 text-center text-accent-light font-semibold text-xs">$0–$29/mo</td>
                <td className="py-3.5 px-4 text-center text-secondary text-xs">Free/OSS</td>
                <td className="py-3.5 px-4 text-center text-secondary text-xs">$49+/mo</td>
                <td className="py-3.5 px-4 text-center text-secondary text-xs">$50k–90k eng</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

// ── How It Works ───────────────────────────────────────────────────────────────

interface Step {
  number: string
  title: string
  description: string
  code: string
}

const steps: Step[] = [
  {
    number: '01',
    title: 'Register your agent',
    description: 'Create an agent in the dashboard. Get a unique API key instantly.',
    code: 'POST /api/v1/agents\n→ { api_key: "nxai_..." }',
  },
  {
    number: '02',
    title: 'Configure permissions',
    description: 'Grant the exact tools your agent needs. Nothing more.',
    code: 'POST /api/v1/agents/{id}/permissions\n→ { tool_name: "read_file" }',
  },
  {
    number: '03',
    title: 'Make tool calls',
    description: 'Point your MCP client at Arbiter. All calls proxied, cached, and logged.',
    code: 'POST /api/v1/proxy/tool-call\n→ { server_name, tool_name, params }',
  },
]

function HowItWorks(): React.ReactElement {
  return (
    <section className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">Up and running in minutes</h2>
        </div>

        <div className="relative grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="hidden md:block absolute top-6 left-1/6 right-1/6 h-px bg-border-strong" />

          {steps.map((step) => (
            <div key={step.number} className="relative flex flex-col gap-4">
              <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center flex-shrink-0">
                <span className="font-mono font-semibold text-base tracking-tight" style={{ color: 'rgba(255,255,255,0.95)' }}>{step.number}</span>
              </div>

              <div>
                <h3 className="font-display text-primary font-semibold text-sm tracking-tight mb-1.5">{step.title}</h3>
                <p className="text-secondary text-sm mb-3">{step.description}</p>
                <pre className="bg-elevated border border-border rounded-lg px-4 py-3 font-mono text-xs text-teal-light leading-relaxed whitespace-pre-wrap">
                  {step.code}
                </pre>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── Pricing ────────────────────────────────────────────────────────────────────

interface PricingTier {
  name: string
  price: string
  period?: string
  features: string[]
  cta: string
  ctaHref: string
  highlighted?: boolean
}

const pricingTiers: PricingTier[] = [
  {
    name: 'Free',
    price: '$0',
    period: '/mo',
    features: [
      '2 agents',
      '5 MCP servers',
      '5,000 tool calls/mo',
      '10 vault secrets',
      'Community support',
    ],
    cta: 'Get Started Free',
    ctaHref: '/register',
  },
  {
    name: 'Pro',
    price: '$29',
    period: '/mo',
    features: [
      '25 agents',
      '50 MCP servers',
      '100,000 tool calls/mo',
      '100 vault secrets',
      'Priority support',
    ],
    cta: 'Upgrade to Pro',
    ctaHref: '/register',
    highlighted: true,
  },
  {
    name: 'Enterprise',
    price: 'Custom',
    features: [
      'Unlimited everything',
      'Custom SLA',
      'Dedicated support',
      'SSO',
      'Self-hosted option',
    ],
    cta: 'Contact Sales',
    ctaHref: `mailto:${SUPPORT_EMAIL}`,
  },
]

function Pricing(): React.ReactElement {
  const { user } = useAuth()
  const navigate = useNavigate()

  function handleProCta(): void {
    if (user) {
      navigate('/settings?tab=billing')
    } else {
      navigate('/register')
    }
  }

  return (
    <section className="py-24 px-6 bg-surface/30" id="pricing">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">Start free. Upgrade when you need to.</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
          {pricingTiers.map((tier) => (
            <div
              key={tier.name}
              className={`flex flex-col rounded-2xl p-7 transition-colors duration-200 ${
                tier.highlighted
                  ? 'bg-surface border border-border-accent shadow-[0_0_32px_rgba(217,119,6,0.10)]'
                  : 'bg-surface border border-border'
              }`}
            >
              {tier.highlighted && (
                <div className="inline-flex self-start mb-4 px-2.5 py-0.5 rounded-full bg-accent/15 border border-border-accent">
                  <span className="text-accent-light text-xs font-medium tracking-wide">Most popular</span>
                </div>
              )}
              <p className="font-display text-primary font-semibold text-base tracking-tight mb-1">{tier.name}</p>
              <div className="flex items-baseline gap-0.5 mb-5">
                <span className="font-display text-3xl font-semibold tracking-tight text-primary">{tier.price}</span>
                {tier.period && <span className="text-muted text-sm">{tier.period}</span>}
              </div>

              <ul className="flex-1 space-y-2.5 mb-7">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-center gap-2.5 text-sm text-secondary">
                    <Check size={14} strokeWidth={2.5} className="text-success flex-shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>

              {tier.ctaHref.startsWith('mailto') ? (
                <a
                  href={tier.ctaHref}
                  className="press block text-center border border-border-strong hover:border-border-accent text-secondary hover:text-accent-light px-4 py-2.5 rounded-xl text-sm font-medium transition-colors duration-150 ease-[var(--ease-out-expo)]"
                >
                  {tier.cta}
                </a>
              ) : tier.highlighted ? (
                <button
                  type="button"
                  onClick={handleProCta}
                  className="press block w-full text-center px-4 py-2.5 rounded-xl text-sm font-semibold transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] bg-accent hover:bg-accent-light text-white hover-glow-standard"
                >
                  {user ? 'Go to Billing' : tier.cta}
                </button>
              ) : (
                <Link
                  to={tier.ctaHref}
                  className="press block text-center px-4 py-2.5 rounded-xl text-sm font-semibold transition-colors duration-150 ease-[var(--ease-out-expo)] border border-border-strong hover:border-border-accent text-secondary hover:text-accent-light"
                >
                  {tier.cta}
                </Link>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ── FAQ ────────────────────────────────────────────────────────────────────────

interface FAQItem {
  question: string
  answer: string
}

const faqItems: FAQItem[] = [
  {
    question: 'What is MCP?',
    answer:
      'Model Context Protocol (MCP) is an open standard for AI agents to call tools safely. It defines a structured way for AI models to interact with external systems, files, and APIs.',
  },
  {
    question: 'How does Arbiter differ from calling MCP servers directly?',
    answer:
      'Arbiter adds identity, access control, secrets management, semantic caching, and full observability on top of any MCP server. Instead of each agent connecting directly to each server, all traffic flows through Arbiter where it can be audited, cached, and controlled.',
  },
  {
    question: 'Is my data secure?',
    answer:
      'All secrets are encrypted with AES-256-GCM before storage. API keys are hashed using bcrypt. We never store plaintext credentials or secret values. Secrets are only decrypted in memory at the moment of injection.',
  },
  {
    question: 'Can I self-host?',
    answer:
      'Yes. The Enterprise plan includes a self-hosted option. You get full source access and deployment support. Contact sales to discuss your infrastructure requirements.',
  },
  {
    question: 'What MCP clients are supported?',
    answer:
      'Any client that supports the MCP spec, including Claude Desktop, Continue, Cursor, and custom clients built with the official MCP SDK. Arbiter is a drop-in gateway. Just change your base URL.',
  },
]

function FAQ(): React.ReactElement {
  const [openIdx, setOpenIdx] = useState<number | null>(null)

  return (
    <section className="py-24 px-6">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">Common questions</h2>
        </div>

        <div className="space-y-3">
          {faqItems.map((item, idx) => {
            const isOpen = openIdx === idx
            return (
              <div
                key={item.question}
                className="bg-surface border border-border hover:border-border-strong rounded-xl overflow-hidden transition-colors duration-200"
              >
                <button
                  type="button"
                  onClick={() => setOpenIdx(isOpen ? null : idx)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left gap-4 hover:bg-white/[0.02] transition-colors duration-150"
                >
                  <span className="text-primary text-sm font-medium">{item.question}</span>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    className={`text-secondary flex-shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
                  >
                    <polyline points="6 9 12 15 18 9"/>
                  </svg>
                </button>
                {isOpen && (
                  <div className="px-5 pb-5">
                    <p className="text-secondary text-sm">{item.answer}</p>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

// ── Contact ────────────────────────────────────────────────────────────────────

function Contact(): React.ReactElement {
  return (
    <section className="py-24 px-6 bg-surface/30">
      <div className="max-w-2xl mx-auto text-center">
        <h2 className="text-2xl font-display font-semibold text-primary mb-3">Have a question?</h2>
        <p className="text-secondary text-base mb-10">
          If something is unclear or you need help getting set up, send us a message. We respond quickly.
        </p>
        <a
          href={`mailto:${SUPPORT_EMAIL}?subject=Arbiter Inquiry`}
          className="press inline-flex items-center gap-2 bg-accent hover:bg-accent-light text-white font-semibold px-6 py-3 rounded-xl transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover-glow-standard text-sm"
        >
          {SUPPORT_EMAIL}
        </a>
      </div>
    </section>
  )
}

// ── Footer ─────────────────────────────────────────────────────────────────────

function Footer(): React.ReactElement {
  return (
    <footer className="bg-surface border-t border-border px-6 py-8">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <ArbiterMark size={22} />
          <span className="font-display text-primary font-semibold text-sm tracking-tight">Arbiter</span>
          <span className="text-muted text-xs ml-2">© 2026 Arbiter. All rights reserved.</span>
        </div>

        <div className="flex items-center gap-5">
          <Link to="/" className="text-secondary hover:text-primary text-xs transition-colors">
            Dashboard
          </Link>
          <Link to="/docs" className="text-secondary hover:text-primary text-xs transition-colors">
            API Docs
          </Link>
          <Link to="/privacy" className="text-secondary hover:text-primary text-xs transition-colors">
            Privacy
          </Link>
          <Link to="/terms" className="text-secondary hover:text-primary text-xs transition-colors">
            Terms
          </Link>
          <Link to="/security" className="text-secondary hover:text-primary text-xs transition-colors">
            Security
          </Link>
          <Link to="/changelog" className="text-secondary hover:text-primary text-xs transition-colors">
            Changelog
          </Link>
          <a
            href={`mailto:${SUPPORT_EMAIL}`}
            className="text-secondary hover:text-primary text-xs transition-colors"
          >
            Contact
          </a>
        </div>
      </div>
    </footer>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

interface LandingProps { initialModal?: AuthMode }

function Landing({ initialModal }: LandingProps): React.ReactElement {
  const navigate = useNavigate()
  const [authModal, setAuthModal] = useState<AuthMode | null>(initialModal ?? null)

  function openModal(mode: AuthMode): void { setAuthModal(mode) }
  function closeModal(): void {
    setAuthModal(null)
    if (initialModal) navigate('/', { replace: true })
  }

  return (
    <div data-theme="dark" className="min-h-screen text-primary">
      <Navbar onSignIn={() => openModal('login')} onGetStarted={() => openModal('register')} />
      <div>
        <Hero onGetStarted={() => openModal('register')} onSignIn={() => openModal('login')} />
        <ProductProof />
        <Comparison />
        <HowItWorks />
        <Pricing />
        <FAQ />
        <Contact />
        <Footer />
      </div>

      {authModal && (
        <AuthModal initialMode={authModal} onClose={closeModal} />
      )}
    </div>
  )
}

export default Landing
