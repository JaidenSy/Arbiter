/**
 * Arbiter — Marketing landing page.
 *
 * Shown to unauthenticated users at /.
 * No sidebar. Standalone dark layout.
 */

import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArbiterMark } from '../components/ArbiterLogo'

const SUPPORT_EMAIL: string =
  (import.meta.env.VITE_SUPPORT_EMAIL as string | undefined) ?? 'jaidensy07@gmail.com'

// ── Navbar ─────────────────────────────────────────────────────────────────────

function Navbar(): React.ReactElement {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-base/80 backdrop-blur-md border-b border-white/[0.06]">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-2.5">
          <ArbiterMark size={30} />
          <span className="text-primary font-semibold text-sm tracking-wide">Arbiter</span>
        </div>

        {/* Right nav */}
        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="text-secondary hover:text-primary border border-white/[0.1] hover:border-white/[0.2] px-4 py-1.5 rounded-lg text-sm transition-all"
          >
            Sign In
          </Link>
          <Link
            to="/register"
            className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition-all hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]"
          >
            Get Started Free
          </Link>
        </div>
      </div>
    </nav>
  )
}

// ── Hero ───────────────────────────────────────────────────────────────────────

function Hero(): React.ReactElement {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center text-center px-6 overflow-hidden">
      {/* Background glows */}
      <div className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full bg-accent/10 blur-[140px] pointer-events-none" />
      <div className="absolute -bottom-40 -right-40 w-[500px] h-[500px] rounded-full bg-teal/8 blur-[140px] pointer-events-none" />

      {/* Dot grid */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage: 'radial-gradient(circle, #A78BFA 1px, transparent 1px)',
          backgroundSize: '28px 28px',
        }}
      />

      <div className="relative max-w-3xl mx-auto animate-fade-in">
        {/* Beta badge */}
        <div className="inline-flex items-center gap-2 bg-accent/10 border border-accent/20 rounded-full px-3 py-1 mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          <span className="text-accent-light text-xs font-medium">Now in Beta</span>
        </div>

        {/* Headline */}
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-primary leading-tight mb-6">
          The Identity Layer for{' '}
          <span className="gradient-text">Your AI Agents</span>
        </h1>

        {/* Subheadline */}
        <p className="text-secondary text-lg sm:text-xl max-w-2xl mx-auto leading-relaxed mb-10">
          Arbiter gives every AI agent a cryptographic identity, fine-grained tool permissions, an
          encrypted secrets vault, and full chain observability — all through a single MCP gateway.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-6">
          <Link
            to="/register"
            className="bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white font-semibold px-6 py-3 rounded-xl transition-all hover:shadow-[0_0_24px_rgba(124,58,237,0.35)] text-sm"
          >
            Start for Free →
          </Link>
          <Link
            to="/login"
            className="text-secondary hover:text-primary border border-white/[0.1] hover:border-white/[0.2] px-6 py-3 rounded-xl text-sm transition-all"
          >
            Sign In
          </Link>
        </div>

        <p className="text-muted text-xs">
          Free plan includes 3 agents · 1,000 tool calls/mo · No credit card required
        </p>

        {/* Terminal demo */}
        <div className="mt-14 bg-surface/80 backdrop-blur-sm border border-white/[0.08] rounded-2xl p-5 text-left max-w-xl mx-auto shadow-2xl">
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
          <h2 className="text-3xl font-bold text-primary mb-4">
            Everything your agents need
          </h2>
          <div className="w-16 h-0.5 bg-gradient-to-r from-accent to-teal mx-auto" />
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((f) => (
            <div
              key={f.title}
              className="bg-surface border border-white/[0.07] rounded-2xl p-6 hover:border-accent/30 transition-all group"
            >
              <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center text-accent-light mb-4 group-hover:bg-accent/15 transition-colors">
                {f.icon}
              </div>
              <h3 className="text-primary font-semibold text-sm mb-2">{f.title}</h3>
              <p className="text-secondary text-sm leading-relaxed">{f.description}</p>
            </div>
          ))}
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
          <h2 className="text-3xl font-bold text-primary mb-4">Up and running in minutes</h2>
          <div className="w-16 h-0.5 bg-gradient-to-r from-accent to-teal mx-auto" />
        </div>

        <div className="relative grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Connecting line (desktop) */}
          <div className="hidden md:block absolute top-8 left-1/6 right-1/6 h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" />

          {steps.map((step) => (
            <div key={step.number} className="relative flex flex-col gap-4">
              {/* Number badge */}
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent to-violet-700 flex items-center justify-center flex-shrink-0 shadow-[0_0_24px_rgba(124,58,237,0.25)]">
                <span className="font-mono font-bold text-white text-lg">{step.number}</span>
              </div>

              <div>
                <h3 className="text-primary font-semibold text-sm mb-1.5">{step.title}</h3>
                <p className="text-secondary text-sm leading-relaxed mb-3">{step.description}</p>
                <pre className="bg-elevated border border-white/[0.07] rounded-lg px-4 py-3 font-mono text-xs text-teal-light leading-relaxed whitespace-pre-wrap">
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
  return (
    <section className="py-24 px-6" id="pricing">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-3xl font-bold text-primary mb-4">Simple, transparent pricing</h2>
          <div className="w-16 h-0.5 bg-gradient-to-r from-accent to-teal mx-auto" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
          {pricingTiers.map((tier) => (
            <div
              key={tier.name}
              className={`flex flex-col rounded-2xl p-7 transition-all ${
                tier.highlighted
                  ? 'bg-surface border border-accent/40 glow-accent scale-[1.03] shadow-2xl'
                  : 'bg-surface border border-white/[0.07]'
              }`}
            >
              {tier.highlighted && (
                <div className="inline-flex self-start mb-4 px-2.5 py-0.5 rounded-full bg-accent/15 border border-accent/30">
                  <span className="text-accent-light text-xs font-medium">Most popular</span>
                </div>
              )}
              <p className="text-primary font-bold text-lg mb-1">{tier.name}</p>
              <div className="flex items-baseline gap-0.5 mb-5">
                <span className="text-3xl font-bold text-primary">{tier.price}</span>
                {tier.period && <span className="text-secondary text-sm">{tier.period}</span>}
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
                  className="block text-center border border-white/[0.1] hover:border-accent/50 text-secondary hover:text-accent-light px-4 py-2.5 rounded-xl text-sm font-medium transition-all"
                >
                  {tier.cta}
                </a>
              ) : (
                <Link
                  to={tier.ctaHref}
                  className={`block text-center px-4 py-2.5 rounded-xl text-sm font-semibold transition-all ${
                    tier.highlighted
                      ? 'bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white hover:shadow-[0_0_16px_rgba(124,58,237,0.3)]'
                      : 'border border-white/[0.1] hover:border-accent/50 text-secondary hover:text-accent-light'
                  }`}
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
          <h2 className="text-3xl font-bold text-primary mb-4">Common questions</h2>
          <div className="w-16 h-0.5 bg-gradient-to-r from-accent to-teal mx-auto" />
        </div>

        <div className="space-y-3">
          {faqItems.map((item, idx) => {
            const isOpen = openIdx === idx
            return (
              <div
                key={item.question}
                className="bg-surface border border-white/[0.07] rounded-xl overflow-hidden transition-all"
              >
                <button
                  type="button"
                  onClick={() => setOpenIdx(isOpen ? null : idx)}
                  className="w-full flex items-center justify-between px-5 py-4 text-left gap-4"
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
          className="inline-flex items-center gap-2 bg-gradient-to-r from-accent to-violet-600 hover:from-violet-500 hover:to-violet-700 text-white font-semibold px-6 py-3 rounded-xl transition-all hover:shadow-[0_0_24px_rgba(124,58,237,0.35)] text-sm"
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
    <footer className="bg-surface border-t border-white/[0.06] px-6 py-8">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Left — logo + copyright */}
        <div className="flex items-center gap-2.5">
          <ArbiterMark size={24} />
          <span className="text-primary font-semibold text-sm">Arbiter</span>
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

function Landing(): React.ReactElement {
  return (
    <div data-theme="dark" className="min-h-screen bg-base text-primary">
      <Navbar />
      {/* Offset for fixed navbar */}
      <div className="pt-14">
        <Hero />
        <Features />
        <HowItWorks />
        <Pricing />
        <FAQ />
        <Contact />
        <Footer />
      </div>
    </div>
  )
}

export default Landing
