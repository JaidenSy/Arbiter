/**
 * Arbiter: Marketing landing page.
 *
 * Shown to unauthenticated users at /.
 * No sidebar. Standalone dark layout.
 */

import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArbiterMark } from '../components/ArbiterLogo'
import AuthModal, { type AuthMode } from '../components/AuthModal'
import HeroBackground from '../components/HeroBackground'
import HeroArchDiagram from '../components/HeroArchDiagram'
import DashboardPreview from '../components/DashboardPreview'
import WorksWith from '../components/WorksWith'
import FeatureShowcase from '../components/FeatureShowcase'
import GatewayConnectedCTA from '../components/GatewayConnectedCTA'
import { useScrollReveal } from '../hooks/useScrollReveal'
import { RevealGroup } from '../components/RevealGroup'
import PricingTiers from '../components/PricingTiers'
import { SUPPORT_EMAIL } from '../components/pricingData'

// ── Hero demo ─────────────────────────────────────────────────────────────────

const GITHUB_URL = 'https://github.com/JaidenSy/Arbiter'

function GitHubIcon({ size = 15 }: { size?: number }): React.ReactElement {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 .5C5.37.5 0 5.87 0 12.5c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58v-2.03c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.11-.78.42-1.3.76-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6.01 0c2.29-1.55 3.3-1.23 3.3-1.23.65 1.66.24 2.88.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.61-2.8 5.62-5.48 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.22.69.83.58A12 12 0 0 0 24 12.5C24 5.87 18.63.5 12 .5z"/>
    </svg>
  )
}

/**
 * Above-the-fold proof: a real Claude Code session calling tools through Arbiter.
 * A permitted call is served from the semantic cache, a denied tool is blocked by
 * per-agent RBAC at call time, and both land in the audit trail.
 */
function HeroDemo(): React.ReactElement {
  const prefersReduced =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  return (
    <figure
      className="mt-14 max-w-3xl mx-auto animate-fade-in"
      style={{ animationDelay: '260ms' }}
    >
      <div
        className="rounded-lg overflow-hidden"
        style={{
          border: '1px solid rgba(255,255,255,0.09)',
          boxShadow: '0 0 0 1px rgba(61,53,206,0.12) inset, 0 24px 60px rgba(0,0,0,0.45)',
        }}
      >
        {/* Reduced-motion users get a static poster + manual controls, not autoplay. */}
        <video
          src="/demo.mp4"
          poster="/demo-poster.jpg"
          width={1100}
          height={652}
          autoPlay={!prefersReduced}
          loop={!prefersReduced}
          muted
          playsInline
          controls={prefersReduced}
          preload={prefersReduced ? 'none' : 'auto'}
          aria-label="A Claude Code session calling tools through Arbiter: a permitted call is served from the semantic cache, a denied tool is blocked by per-agent RBAC at call time, and both are written to the audit trail."
          className="block w-full h-auto"
        />
      </div>
      <figcaption className="mt-3 text-muted text-xs">
        Real session: a permitted call is served from cache, a denied tool is blocked at call time, both are written to the audit trail.
      </figcaption>
    </figure>
  )
}

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
          <Link
            to="/pricing"
            className="hidden sm:block text-secondary hover:text-primary px-2 py-1.5 text-sm transition-colors duration-150"
          >
            Pricing
          </Link>
          <Link
            to="/docs"
            className="hidden sm:block text-secondary hover:text-primary px-2 py-1.5 text-sm transition-colors duration-150"
          >
            Docs
          </Link>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:inline-flex items-center gap-1.5 text-secondary hover:text-primary px-2 py-1.5 text-sm transition-colors duration-150"
          >
            <GitHubIcon /> GitHub
          </a>
          <button
            onClick={onSignIn}
            className="press text-secondary hover:text-primary border border-border-strong hover:border-border-strong px-4 py-2.5 rounded-lg text-sm transition-colors duration-150 ease-[var(--ease-out-expo)]"
          >
            Sign In
          </button>
          <button
            onClick={onGetStarted}
            className="press bg-accent hover:bg-accent-light text-white text-sm font-semibold px-4 py-2.5 rounded-lg transition-colors duration-150 ease-[var(--ease-out-expo)]"
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
  const [spot, setSpot]           = useState({ x: 50, y: 35 })
  const [isHovering, setIsHovering] = useState(false)

  function handleMouseMove(e: React.MouseEvent<HTMLElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    setSpot({
      x: ((e.clientX - rect.left) / rect.width) * 100,
      y: ((e.clientY - rect.top)  / rect.height) * 100,
    })
  }

  return (
    <section
      className="relative min-h-screen flex flex-col items-center justify-center text-center px-6 overflow-hidden"
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {/* Background: dot grid + ambient glow */}
      <HeroBackground />

      {/* Mouse spotlight: illuminates dot grid on hover */}
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden
        style={{
          background: `radial-gradient(circle 380px at ${spot.x}% ${spot.y}%, rgba(99,88,230,0.22) 0%, rgba(61,53,206,0.08) 45%, transparent 70%)`,
          opacity: isHovering ? 1 : 0,
          transition: 'opacity 400ms ease-out',
          mixBlendMode: 'screen',
        }}
      />

      {/* Bottom fade: blends hero into sections below */}
      <div
        className="absolute bottom-0 left-0 right-0 h-52 pointer-events-none"
        style={{ background: 'linear-gradient(to bottom, transparent, var(--color-base))' }}
        aria-hidden
      />

      <div className="relative max-w-3xl mx-auto pt-28 sm:pt-24 lg:pt-20">
        {/* Hero headline */}
        <h1
          className="hero-display text-primary mb-6 animate-fade-in"
          style={{ animationDelay: '60ms' }}
        >
          Your AI agents are running
          <br />
          <span className="text-secondary">without guardrails.</span>
        </h1>

        {/* Subheadline */}
        <p
          className="text-secondary text-base sm:text-lg max-w-2xl mx-auto leading-relaxed mb-10 animate-fade-in"
          style={{ animationDelay: '120ms' }}
        >
          Shared credentials, no audit trail, agents that can call any tool they want.
          Arbiter fixes all of it: cryptographic agent identity, tool-level permissions,
          an encrypted secrets vault, and full observability, through a single gateway
          that sits in front of your MCP servers (the tool APIs your agents call).
        </p>

        {/* CTAs */}
        <div
          className="flex flex-col sm:flex-row items-center justify-center gap-3 mb-6 animate-fade-in"
          style={{ animationDelay: '180ms' }}
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
          style={{ animationDelay: '180ms' }}
        >
          Free plan includes 2 agents · 5,000 tool calls/mo · No credit card required
        </p>

        {/* Trust strip: open source, self-hosted, source link */}
        <div
          className="mt-4 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 text-xs text-muted animate-fade-in"
          style={{ animationDelay: '200ms' }}
        >
          <span>Apache-2.0</span>
          <span aria-hidden>·</span>
          <span>Self-hosted: no agent traffic or secret leaves your environment</span>
          <span aria-hidden>·</span>
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-secondary hover:text-primary transition-colors"
          >
            <GitHubIcon size={13} /> View source
          </a>
        </div>

        {/* Live product demo (real session) */}
        <HeroDemo />

        <p
          className="mt-4 text-muted text-xs max-w-xl mx-auto animate-fade-in"
          style={{ animationDelay: '280ms' }}
        >
          Secrets stay in an AES-256-GCM vault and are injected at the gateway. They are never
          returned to the agent. Every call, allowed or denied, is written to the audit trail.
        </p>
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
  const headingRef = useScrollReveal<HTMLHeadingElement>()
  return (
    <section className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 ref={headingRef} className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">
            Identity. Permissions. Secrets. Observability.
          </h2>
        </div>

        {/* Grid: RevealGroup staggers cards on scroll entry */}
        <RevealGroup className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5" stagger={60}>
          {features.map((f, i) => {
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
                <div className="flex items-center gap-2.5 mb-3">
                  <span className="text-accent-light flex-shrink-0">{f.icon}</span>
                  <h3 className="font-display text-primary font-semibold text-sm tracking-tight">{f.title}</h3>
                </div>
                <p className="text-secondary text-sm leading-relaxed">{f.description}</p>
              </div>
            )
          })}
        </RevealGroup>
      </div>
    </section>
  )
}

// ── Comparison ─────────────────────────────────────────────────────────────────

function Comparison(): React.ReactElement {
  const headingRef = useScrollReveal<HTMLHeadingElement>()
  const subheadRef = useScrollReveal<HTMLParagraphElement>({ delay: 80 })
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
    <section className="py-24 px-6 bg-surface/30">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <h2 ref={headingRef} className="font-display text-3xl font-semibold tracking-tight text-primary mb-6">How Arbiter compares</h2>
          <p ref={subheadRef} className="text-secondary text-base max-w-xl mx-auto">
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

// ── Pricing ────────────────────────────────────────────────────────────────────

function Pricing(): React.ReactElement {
  const headingRef = useScrollReveal<HTMLHeadingElement>()

  return (
    <section className="py-24 px-6" id="pricing">
      <div className="max-w-5xl mx-auto">
        <div className="text-center mb-16">
          <h2 ref={headingRef} className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">Start free. Scale when you need to.</h2>
        </div>
        <PricingTiers showCompareLink />
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
      'Yes. The Arbiter core gateway is open source (Apache 2.0). Clone the repo and run docker compose up. Enterprise adds SSO, SCIM, KMS, dedicated deployment support, and a custom SLA on top of that.',
  },
  {
    question: 'What MCP clients are supported?',
    answer:
      'Any client that supports the MCP spec, including Claude Desktop, Continue, Cursor, and custom clients built with the official MCP SDK. Arbiter is a drop-in gateway. Just change your base URL.',
  },
]

function FAQ(): React.ReactElement {
  const [openIdx, setOpenIdx] = useState<number | null>(null)
  const headingRef = useScrollReveal<HTMLHeadingElement>()

  return (
    <section className="py-24 px-6 bg-surface/30">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-16">
          <h2 ref={headingRef} className="font-display text-3xl font-semibold tracking-tight text-primary mb-4">Common questions</h2>
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

// ── Footer ─────────────────────────────────────────────────────────────────────

function Footer(): React.ReactElement {
  return (
    <footer className="bg-surface border-t border-border px-6 py-8">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Left: logo + copyright */}
        <div className="flex items-center gap-2.5">
          <ArbiterMark size={22} />
          <span className="font-display text-primary font-semibold text-sm tracking-tight">Arbiter</span>
          <span className="text-muted text-xs ml-2">© 2026 Arbiter. All rights reserved.</span>
        </div>

        {/* Right: nav */}
        <div className="flex items-center gap-5">
          <Link to="/" className="text-secondary hover:text-primary text-xs transition-colors">
            Dashboard
          </Link>
          <Link to="/pricing" className="text-secondary hover:text-primary text-xs transition-colors">
            Pricing
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
        <WorksWith />
        <HeroArchDiagram />
        <Features />
        <DashboardPreview />
        <Comparison />
        <FeatureShowcase />
        <Pricing />
        <FAQ />
        <GatewayConnectedCTA onGetStarted={() => openModal('register')} />
        <Footer />
      </div>

      {authModal && (
        <AuthModal initialMode={authModal} onClose={closeModal} />
      )}
    </div>
  )
}

export default Landing
