/**
 * Arbiter — Marketing landing page.
 *
 * Shown to unauthenticated users at /.
 * No sidebar. Standalone dark layout.
 */

import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
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
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <ArbiterMark size={26} />
          <span className="font-display text-primary font-semibold text-sm tracking-tight">Arbiter</span>
        </div>

        {/* Right nav */}
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
      {/* Background — shader gradient + particle mesh */}
      <HeroBackground />

      {/* Aurora overlay — warm amber focal glow from top center */}
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none"
        style={{ background: 'var(--gradient-aurora-hero)' }}
      />

      {/* Dot grid — kept at very low opacity for texture depth */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.025]"
        style={{
          backgroundImage: 'radial-gradient(circle, #F59E0B 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      />

      {/* Bottom fade — blends WebGL hero into ambient-lit sections below */}
      <div
        className="absolute bottom-0 left-0 right-0 h-52 pointer-events-none"
        style={{ background: 'linear-gradient(to bottom, transparent, var(--color-base))' }}
        aria-hidden
      />

      <div className="relative max-w-3xl mx-auto pt-28 sm:pt-24 lg:pt-20">
        {/* Kicker label */}
        <p
          className="kicker mb-5"
          style={{ animationDelay: '0ms' }}
        >
          MCP Security Gateway
        </p>

        {/* Hero headline — staggered entrance */}
        <h1
          className="hero-display text-primary mb-6 animate-fade-in"
          style={{ animationDelay: '60ms', animationFillMode: 'both' }}
        >
          Your AI agents are running
          <br />
          <span className="text-secondary">without guardrails.</span>
        </h1>

        {/* Subheadline */}
        <p
          className="text-secondary text-base sm:text-lg max-w-2xl mx-auto leading-relaxed mb-10 animate-fade-in"
          style={{ animationDelay: '120ms', animationFillMode: 'both' }}
        >
          Shared credentials, no audit trail, agents that can call any tool they want.
          Arbiter fixes all of it — cryptographic agent identity, tool-level permissions,
          an encrypted secrets vault, and full observability through a single MCP gateway.
        </p>

        {/* CTAs — hero-glow only on primary CTA */}
        <div
          className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-6 animate-fade-in"
          style={{ animationDelay: '200ms', animationFillMode: 'both' }}
        >
          <button
            onClick={onGetStarted}
            className="press bg-accent hover:bg-accent-light text-white font-semibold px-6 py-3 rounded-xl transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover-glow-hero text-sm"
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
          Free plan includes 3 agents · 1,000 tool calls/mo · No credit card required
        </p>

        {/* Terminal demo */}
        <div
          className="mt-14 bg-surface/85 backdrop-blur-sm border border-border-strong rounded-2xl p-5 text-left max-w-xl mx-auto shadow-2xl animate-fade-in"
          style={{ animationDelay: '280ms', animationFillMode: 'both' }}
        >
          <div className="flex items-center gap-1.5 mb-4">
            <span className="w-2.5 h-2.5 rounded-full bg-error/70" />
            <span className="w-2.5 h-2.5 rounded-full bg-warning/70" />
            <span className="w-2.5 h-2.5 rounded-full bg-success/70" />
          </div>
          <pre className="font-mono text-xs text-secondary leading-relaxed">
            <span className="text-muted">$</span>{' '}
            <span className="text-teal-light">curl</span>{' '}
            <span className="text-primary">-X POST https://your-arbiter.railway.app/mcp \</span>
            {'\n'}
            {'  '}<span className="text-accent-light">-H</span>{' '}
            <span className="text-success">"Authorization: Bearer nxai_abc123..."</span>
            {'\n'}
            {'  '}<span className="text-accent-light">-d</span>{' '}
            <span className="text-success">'{`{"tool":"read_file","path":"/app/config.json"}`}'</span>
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

// ── Features ───────────────────────────────────────────────────────────────────

interface Feature {
  icon: React.ReactElement
  title: string
  description: string
}

const features: Feature[] = [
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 2L2 7l10 5 10-5-10-5z"/>
        <path d="M2 17l10 5 10-5M2 12l10 5 10-5"/>
      </svg>
    ),
    title: 'Agent Identity',
    description: 'Every agent gets a unique cryptographic API key. No shared credentials, no identity confusion.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="3" y="11" width="18" height="11" rx="1"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
      </svg>
    ),
    title: 'Tool-Level Permissions',
    description: 'Grant and revoke individual tool access per agent. Principle of least privilege, enforced.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <rect x="2" y="3" width="20" height="18" rx="1"/>
        <path d="M8 10h8M8 14h4"/>
        <circle cx="18" cy="18" r="4" fill="none"/>
        <path d="M17 18l1 1 2-2"/>
      </svg>
    ),
    title: 'Encrypted Vault',
    description: 'Store secrets per agent with AES-256-GCM encryption. Secrets never leave the vault unencrypted.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10"/>
        <path d="M12 6v6l4 2"/>
      </svg>
    ),
    title: 'Semantic Cache',
    description: 'Identical tool calls return cached responses instantly. Reduce latency and API costs automatically.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    ),
    title: 'Full Observability',
    description: 'Every tool call logged with full request/response traces. Know exactly what your agents are doing.',
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="3"/>
        <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
      </svg>
    ),
    title: 'MCP Native',
    description: 'Drop-in compatible with any MCP client. One gateway URL, infinite agents.',
  },
]

function Features(): React.ReactElement {
  return (
    <section className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-16">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">
            Everything your agents need
          </h2>
          <div className="w-10 h-px bg-accent/60 mx-auto" />
        </div>

        {/* Grid — 4-col desktop bento: wide(2)+narrow(1)+narrow(1) / narrow(1)+wide(2)+narrow(1) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {features.map((f, i) => {
            // Agent Identity (0) and Full Observability (4) span 2 cols
            const isWide = i === 0 || i === 4
            return (
              <div
                key={f.title}
                className={[
                  'bg-surface border border-border rounded-2xl p-6',
                  'hover:border-border-strong transition-colors duration-200 ease-[var(--ease-out-expo)] group',
                  isWide ? 'lg:col-span-2 sm:col-span-2' : '',
                ].filter(Boolean).join(' ')}
              >
                <div className="w-9 h-9 rounded-lg bg-accent/[0.08] border border-border-accent flex items-center justify-center text-accent-light mb-4 group-hover:bg-accent/[0.12] transition-colors duration-200">
                  {f.icon}
                </div>
                <h3 className="font-display text-primary font-semibold text-sm tracking-tight mb-2">{f.title}</h3>
                <p className="text-secondary text-sm leading-relaxed">{f.description}</p>
              </div>
            )
          })}
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
    { feature: 'Per-agent identity',         arbiter: true,      litellm: false,     portkey: false,     diy: '~3 months' },
    { feature: 'Tool-level RBAC',            arbiter: true,      litellm: false,     portkey: false,     diy: '~2 months' },
    { feature: 'Encrypted secrets vault',    arbiter: true,      litellm: false,     portkey: false,     diy: '~2 months' },
    { feature: 'Semantic cache (pgvector)',  arbiter: true,      litellm: 'partial', portkey: 'partial', diy: '~3 months' },
    { feature: 'Full request/response audit', arbiter: true,     litellm: 'partial', portkey: true,      diy: '~1 month'  },
    { feature: 'MCP protocol native',        arbiter: true,      litellm: false,     portkey: false,     diy: 'depends'   },
    { feature: 'Self-hosted',                arbiter: true,      litellm: true,      portkey: false,     diy: true,        enterpriseOnly: true },
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
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">How Arbiter compares</h2>
          <div className="w-10 h-px bg-accent/60 mx-auto mb-6" />
          <p className="text-secondary text-base max-w-xl mx-auto">
            LiteLLM and Portkey solve LLM routing. Arbiter solves MCP security.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border-strong">
                <th className="text-left py-3 pr-6 text-secondary font-normal w-[45%]" />
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
                  <td className="py-3.5 pr-6 text-secondary">
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
                <td className="py-3.5 pr-6 text-primary font-semibold">Cost</td>
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
    code: 'POST /api/v1/tool-permissions\n→ { tool: "read_file" }',
  },
  {
    number: '03',
    title: 'Make tool calls',
    description: 'Point your MCP client at Arbiter. All calls proxied, cached, and logged.',
    code: 'mcp_client.connect(\n  "https://your-arbiter.railway.app"\n)',
  },
]

function HowItWorks(): React.ReactElement {
  return (
    <section className="py-24 px-6 bg-surface/30">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">Up and running in minutes</h2>
          <div className="w-10 h-px bg-accent/60 mx-auto" />
        </div>

        <div className="relative grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Connecting line (desktop) */}
          <div className="hidden md:block absolute top-6 left-1/6 right-1/6 h-px bg-border-strong" />

          {steps.map((step) => (
            <div key={step.number} className="relative flex flex-col gap-4">
              {/* Number badge — solid amber, no purple glow */}
              <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center flex-shrink-0">
                <span className="font-mono font-semibold text-base tracking-tight" style={{ color: 'rgba(255,255,255,0.95)' }}>{step.number}</span>
              </div>

              <div>
                <h3 className="font-display text-primary font-semibold text-sm tracking-tight mb-1.5">{step.title}</h3>
                <p className="text-secondary text-sm leading-relaxed mb-3">{step.description}</p>
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
      '3 agents',
      '5 MCP servers',
      '1,000 tool calls/mo',
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
    <section className="py-24 px-6" id="pricing">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">Simple, transparent pricing</h2>
          <div className="w-10 h-px bg-accent/60 mx-auto" />
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
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-success flex-shrink-0">
                      <polyline points="20 6 9 17 4 12"/>
                    </svg>
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
      'Yes — the Enterprise plan includes a self-hosted option. You get full source access and deployment support. Contact sales to discuss your infrastructure requirements.',
  },
  {
    question: 'What MCP clients are supported?',
    answer:
      'Any client that supports the MCP spec, including Claude Desktop, Continue, Cursor, and custom clients built with the official MCP SDK. Arbiter is a drop-in gateway — just change your base URL.',
  },
]

function FAQ(): React.ReactElement {
  const [openIdx, setOpenIdx] = useState<number | null>(null)

  return (
    <section className="py-24 px-6 bg-surface/30">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">Common questions</h2>
          <div className="w-10 h-px bg-accent/60 mx-auto" />
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
                    <p className="text-secondary text-sm leading-relaxed">{item.answer}</p>
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
    <section className="py-24 px-6">
      <div className="max-w-2xl mx-auto text-center">
        <h2 className="text-3xl font-bold text-primary mb-4">Questions? We're here.</h2>
        <p className="text-secondary text-base leading-relaxed mb-10">
          Whether you're evaluating Arbiter for your team or need help getting started, reach out.
        </p>
        <a
          href={`mailto:${SUPPORT_EMAIL}?subject=Arbiter Inquiry`}
          className="press inline-flex items-center gap-2 bg-accent hover:bg-accent-light text-white font-semibold px-6 py-3 rounded-xl transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover-glow-standard text-sm"
        >
          Send us a message
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
        {/* Left — logo + copyright */}
        <div className="flex items-center gap-2.5">
          <ArbiterMark size={22} />
          <span className="font-display text-primary font-semibold text-sm tracking-tight">Arbiter</span>
          <span className="text-muted text-xs ml-2">© 2026 Arbiter. All rights reserved.</span>
        </div>

        {/* Right — nav */}
        <div className="flex items-center gap-5">
          <Link to="/login" className="text-secondary hover:text-primary text-xs transition-colors">
            Dashboard
          </Link>
          <Link to="/docs" className="text-secondary hover:text-primary text-xs transition-colors">
            Docs
          </Link>
          <a
            href="/api/v1/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="text-secondary hover:text-primary text-xs transition-colors"
          >
            API Docs
          </a>
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
        <Features />
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
