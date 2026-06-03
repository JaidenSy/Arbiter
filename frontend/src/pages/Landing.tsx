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
    <section className="pt-24 pb-20 px-6 lg:pt-28 lg:pb-24">
      <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-[1fr_460px] gap-14 lg:gap-20 items-start">

        {/* Left — text */}
        <div className="pt-2">
          <h1 className="hero-display text-primary mb-5">
            Your AI agents are running without guardrails.
          </h1>
          <p className="text-secondary text-base sm:text-lg leading-relaxed mb-8 max-w-xl">
            Shared credentials, no audit trail, agents that can call any tool they want.
            Arbiter fixes all of it: cryptographic agent identity, tool-level permissions,
            an encrypted secrets vault, and full observability through a single MCP gateway.
          </p>

          {/* Drop-in proof — the one concrete thing that earns trust before the CTA */}
          <div className="mb-8 font-mono text-xs border border-border rounded-lg px-4 py-3 bg-elevated inline-block leading-relaxed">
            <p className="text-muted mb-1.5 font-sans text-[11px] font-medium">One URL change. That's it.</p>
            <p><span className="line-through text-error/60">https://filesystem.server.io</span></p>
            <p><span className="text-success">https://api.arbiterai.dev/proxy/filesystem</span></p>
          </div>

          <div className="flex flex-col sm:flex-row items-start gap-3 mb-4">
            <button
              onClick={onGetStarted}
              className="press bg-accent hover:bg-accent-light text-white font-semibold px-5 py-2.5 rounded-lg transition-colors duration-150 ease-[var(--ease-out-expo)] text-sm"
            >
              Start for Free
            </button>
            <button
              onClick={onSignIn}
              className="press text-secondary hover:text-primary border border-border-strong hover:border-border-accent px-5 py-2.5 rounded-lg text-sm transition-colors duration-150 ease-[var(--ease-out-expo)]"
            >
              Sign In
            </button>
          </div>
          <p className="text-muted text-xs">Free plan: 2 agents, 5,000 tool calls/mo, no credit card required.</p>
        </div>

        {/* Right — terminal (always dark — self-contained dark surface on light page) */}
        <div
          className="rounded-xl p-5 text-left shadow-2xl overflow-hidden"
          style={{ background: '#0F0F12', border: '1px solid rgba(255,255,255,0.08)' }}
        >
          <div className="flex items-center gap-1.5 mb-4">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(248,113,113,0.7)' }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(251,191,36,0.7)' }} />
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: 'rgba(52,211,153,0.7)' }} />
          </div>
          <pre className="font-mono text-xs leading-relaxed overflow-x-auto" style={{ color: '#A1A1AA' }}>
            <span style={{ color: '#52525B' }}>$</span>{' '}
            <span style={{ color: '#5EEAD4' }}>curl</span>{' '}
            <span style={{ color: '#FAFAFA' }}>-X POST https://api.arbiterai.dev/api/v1/proxy/tool-call \</span>
            {'\n'}
            {'  '}<span style={{ color: '#93C5FD' }}>-H</span>{' '}
            <span style={{ color: '#34D399' }}>"Authorization: Bearer nxai_abc123..."</span>
            {'\n'}
            {'  '}<span style={{ color: '#93C5FD' }}>-d</span>{' '}
            <span style={{ color: '#34D399' }}>'{`{"server_name":"filesystem","tool_name":"read_file","params":{"path":"/app/config.json"}}`}'</span>
            {'\n\n'}
            <span style={{ color: '#52525B' }}># Response</span>
            {'\n'}
            <span style={{ color: '#5EEAD4' }}>{'{'}</span>
            {'\n'}
            {'  '}<span style={{ color: '#93C5FD' }}>"cached"</span>
            <span style={{ color: '#FAFAFA' }}>: </span>
            <span style={{ color: '#FBBF24' }}>false</span>
            <span style={{ color: '#FAFAFA' }}>,</span>
            {'\n'}
            {'  '}<span style={{ color: '#93C5FD' }}>"agent_id"</span>
            <span style={{ color: '#FAFAFA' }}>: </span>
            <span style={{ color: '#34D399' }}>"agt_xyz789"</span>
            <span style={{ color: '#FAFAFA' }}>,</span>
            {'\n'}
            {'  '}<span style={{ color: '#93C5FD' }}>"result"</span>
            <span style={{ color: '#FAFAFA' }}>: {'{'}</span>
            <span style={{ color: '#52525B' }}>...</span>
            <span style={{ color: '#FAFAFA' }}>{'}'}</span>
            {'\n'}
            <span style={{ color: '#5EEAD4' }}>{'}'}</span>
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
    description: 'Granular AI agent access control: grant and revoke tool permissions per agent. Principle of least privilege, enforced.',
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
    <section className="py-20 px-6 border-t border-border">
      <div className="max-w-4xl mx-auto">
        <h2 className="font-display text-2xl font-semibold tracking-tight text-primary mb-2">
          What Arbiter does
        </h2>
        <p className="text-secondary text-sm mb-10">Six things, each one specific.</p>

        <dl className="divide-y divide-border">
          {features.map((f) => (
            <div
              key={f.title}
              className="grid grid-cols-1 sm:grid-cols-[200px_1fr] gap-2 sm:gap-10 py-5 group"
            >
              <dt className="font-semibold text-primary text-sm pt-0.5">{f.title}</dt>
              <dd className="text-secondary text-sm leading-relaxed">{f.description}</dd>
            </div>
          ))}
        </dl>
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
    { feature: 'Self-hosted',                arbiter: true,      litellm: true,      portkey: false,     diy: true,        },
  ]

  function renderCell(val: CellVal): React.ReactNode {
    if (val === true) return check
    if (val === false) return cross
    if (val === 'partial') return <span className="text-warning text-xs font-medium">Partial</span>
    return <span className="text-muted text-xs">{val}</span>
  }

  return (
    <section className="py-20 px-6 border-t border-border">
      <div className="max-w-4xl mx-auto">
        <div className="mb-10">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-primary mb-2">How Arbiter compares</h2>
          <p className="text-secondary text-sm">LiteLLM and Portkey solve LLM routing. Arbiter solves MCP security.</p>
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
                <tr key={row.feature} className={`border-b border-border ${i % 2 === 0 ? 'bg-black/[0.02]' : ''}`}>
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
    <section className="py-20 px-6 border-t border-border">
      <div className="max-w-4xl mx-auto">
        <h2 className="font-display text-2xl font-semibold tracking-tight text-primary mb-2">Up and running in minutes</h2>
        <p className="text-secondary text-sm mb-10">Three steps, each taking less than 60 seconds.</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          {steps.map((step) => (
            <div key={step.number} className="flex flex-col gap-3">
              <span className="font-mono text-xs text-muted font-medium">{step.number}</span>
              <h3 className="font-display text-primary font-semibold text-sm tracking-tight">{step.title}</h3>
              <p className="text-secondary text-sm leading-relaxed">{step.description}</p>
              <pre className="bg-elevated border border-border rounded-lg px-4 py-3 font-mono text-xs text-accent leading-relaxed whitespace-pre-wrap mt-auto">
                {step.code}
              </pre>
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
      'Self-hosted deployment support',
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
    <section className="py-16 px-6 border-t border-border" id="pricing">
      <div className="max-w-4xl mx-auto">
        <div className="mb-10">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-primary mb-2">Simple, transparent pricing</h2>
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
      'Yes. Arbiter is open source (AGPL v3) — clone the repo and run docker compose up. Enterprise adds dedicated deployment support and a custom SLA on top of that.',
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
    <section className="py-20 px-6 border-t border-border">
      <div className="max-w-3xl mx-auto">
        <div className="mb-10">
          <h2 className="font-display text-2xl font-semibold tracking-tight text-primary mb-2">Common questions</h2>
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
                  className="w-full flex items-center justify-between px-5 py-4 text-left gap-4 hover:bg-black/[0.03] transition-colors duration-150"
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
    <div data-theme="light" className="min-h-screen bg-base text-primary">
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
