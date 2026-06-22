/**
 * Arbiter: Pricing page.
 *
 * Route: /pricing (public, no auth required)
 * Tier cards (shared with the landing page), a full feature comparison
 * table, and billing FAQ.  Every row in the comparison table corresponds
 * to a limit or plan gate enforced in the backend: keep it in sync with
 * PLAN_LIMITS and the endpoint-level plan checks.
 */

import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArbiterMark } from '../components/ArbiterLogo'
import PricingTiers from '../components/PricingTiers'
import { SUPPORT_EMAIL } from '../components/pricingData'

// ── Navbar ─────────────────────────────────────────────────────────────────────

function Navbar(): React.ReactElement {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-base/85 backdrop-blur-md border-b border-border">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5">
          <ArbiterMark size={26} />
          <span className="font-display text-primary font-semibold text-sm tracking-tight">Arbiter</span>
        </Link>
        <div className="flex items-center gap-3">
          <Link
            to="/docs"
            className="hidden sm:block text-secondary hover:text-primary px-2 py-1.5 text-sm transition-colors duration-150"
          >
            Docs
          </Link>
          <Link
            to="/login"
            className="text-secondary hover:text-primary border border-border hover:border-border-strong px-4 py-1.5 rounded-lg text-sm transition-colors duration-150"
          >
            Sign In
          </Link>
          <Link
            to="/register"
            className="bg-accent hover:bg-accent-light text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition-colors duration-150"
          >
            Get Started
          </Link>
        </div>
      </div>
    </nav>
  )
}

// ── Feature comparison ─────────────────────────────────────────────────────────

type CellVal = string | boolean

interface ComparisonRow {
  feature: string
  free: CellVal
  pro: CellVal
  enterprise: CellVal
}

interface ComparisonGroup {
  title: string
  rows: ComparisonRow[]
}

const comparisonGroups: ComparisonGroup[] = [
  {
    title: 'Usage limits',
    rows: [
      { feature: 'Agents', free: '2', pro: '25', enterprise: 'Unlimited' },
      { feature: 'MCP servers', free: '3', pro: '50', enterprise: 'Unlimited' },
      { feature: 'Tool calls per month', free: '5,000', pro: '100,000', enterprise: 'Unlimited' },
      { feature: 'Vault secrets', free: '10', pro: '100', enterprise: 'Unlimited' },
      { feature: 'Team members', free: '3', pro: 'Unlimited', enterprise: 'Unlimited' },
    ],
  },
  {
    title: 'Gateway',
    rows: [
      { feature: 'Per-tool RBAC permissions', free: true, pro: true, enterprise: true },
      { feature: 'Session audit log', free: true, pro: true, enterprise: true },
      { feature: 'Secrets vault with injection', free: true, pro: true, enterprise: true },
      { feature: 'Exact-match response caching', free: true, pro: true, enterprise: true },
      { feature: 'Per-tool rate limits', free: true, pro: true, enterprise: true },
      { feature: 'Per-session call budgets', free: true, pro: true, enterprise: true },
      { feature: 'Native MCP endpoint (one URL for any client)', free: true, pro: true, enterprise: true },
      { feature: 'MCP server health monitoring', free: true, pro: true, enterprise: true },
    ],
  },
  {
    title: 'Pro features',
    rows: [
      { feature: 'Semantic caching', free: false, pro: true, enterprise: true },
      { feature: 'Per-agent analytics', free: false, pro: true, enterprise: true },
      { feature: 'Cost tracking per agent & server', free: false, pro: true, enterprise: true },
      { feature: 'Agent anomaly detection (risk score)', free: false, pro: true, enterprise: true },
      { feature: 'Multi-hop execution traces', free: false, pro: true, enterprise: true },
      { feature: 'Audit log export (CSV / JSON)', free: false, pro: true, enterprise: true },
      { feature: 'Webhooks', free: false, pro: true, enterprise: true },
    ],
  },
  {
    title: 'Enterprise',
    rows: [
      { feature: 'SSO', free: false, pro: false, enterprise: true },
      { feature: 'Custom SLA', free: false, pro: false, enterprise: true },
      { feature: 'Self-hosted deployment support', free: false, pro: false, enterprise: true },
      { feature: 'Support', free: 'Community', pro: 'Priority', enterprise: 'Dedicated' },
    ],
  },
]

function Cell({ value }: { value: CellVal }): React.ReactElement {
  if (value === true) {
    return (
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-success inline-block">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
    )
  }
  if (value === false) {
    return <span className="text-muted">—</span>
  }
  return <span className="text-secondary text-xs">{value}</span>
}

function ComparisonTable(): React.ReactElement {
  return (
    <section className="py-16 px-6">
      <div className="max-w-4xl mx-auto">
        <h2 className="font-display text-2xl font-semibold tracking-tight text-primary mb-10 text-center">
          Compare plans
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse min-w-[560px]">
            <thead>
              <tr className="border-b border-border-strong">
                <th className="text-left py-3 px-4 text-secondary font-medium text-xs uppercase tracking-wider">Feature</th>
                <th className="text-center py-3 px-4 text-primary font-semibold text-xs w-28">Free</th>
                <th className="text-center py-3 px-4 text-accent-light font-semibold text-xs w-28">Pro</th>
                <th className="text-center py-3 px-4 text-primary font-semibold text-xs w-28">Enterprise</th>
              </tr>
            </thead>
            <tbody>
              {comparisonGroups.map((group) => (
                <React.Fragment key={group.title}>
                  <tr>
                    <td colSpan={4} className="pt-8 pb-2 px-4">
                      <span className="text-muted text-xs font-semibold uppercase tracking-wider">{group.title}</span>
                    </td>
                  </tr>
                  {group.rows.map((row) => (
                    <tr key={row.feature} className="border-b border-border">
                      <td className="py-3 px-4 text-secondary">{row.feature}</td>
                      <td className="py-3 px-4 text-center"><Cell value={row.free} /></td>
                      <td className="py-3 px-4 text-center"><Cell value={row.pro} /></td>
                      <td className="py-3 px-4 text-center"><Cell value={row.enterprise} /></td>
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

// ── Billing FAQ ────────────────────────────────────────────────────────────────

interface FAQItem {
  question: string
  answer: string
}

const faqItems: FAQItem[] = [
  {
    question: 'What happens when I hit my monthly tool-call limit?',
    answer:
      'Further tool calls return HTTP 429 until the quota resets on the first of the month (UTC). There is a 5% grace buffer past the limit, and the org owner gets an email alert at 80% and 100% of quota, so agents don’t fail silently.',
  },
  {
    question: 'Do cached responses count against my quota?',
    answer:
      'No. Cache hits skip the quota check entirely. Repeated identical calls from your agents are free. The dashboard shows how much upstream cost the cache saved you each month.',
  },
  {
    question: 'How do I upgrade, downgrade, or cancel?',
    answer:
      'Upgrade from Settings → Billing. Checkout is handled by Stripe. Cancel any time from the billing portal; your org returns to the Free plan when the subscription ends. Your agents, servers, and audit history stay intact.',
  },
  {
    question: 'Can I self-host Arbiter instead of paying?',
    answer:
      'Yes. The Arbiter core gateway is open source (Apache 2.0). Clone the repo and run docker compose up. The paid tiers are for the hosted gateway; Enterprise adds SSO, dedicated deployment support, and a custom SLA.',
  },
  {
    question: 'What counts as a tool call?',
    answer:
      'One proxied request from an agent to an MCP server tool. RBAC denials and cache hits do not count. Quotas apply per organization, not per agent.',
  },
]

function BillingFAQ(): React.ReactElement {
  const [openIdx, setOpenIdx] = useState<number | null>(null)

  return (
    <section className="py-16 px-6 bg-surface/30">
      <div className="max-w-3xl mx-auto">
        <h2 className="font-display text-2xl font-semibold tracking-tight text-primary mb-10 text-center">
          Billing questions
        </h2>
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

        <p className="text-center text-muted text-xs mt-8">
          Something else?{' '}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-accent-light hover:text-primary transition-colors">
            {SUPPORT_EMAIL}
          </a>
        </p>
      </div>
    </section>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

function Pricing(): React.ReactElement {
  return (
    <div data-theme="dark" className="min-h-screen text-primary">
      <Navbar />
      <main className="pt-14">
        <section className="pt-20 pb-4 px-6">
          <div className="max-w-5xl mx-auto">
            <div className="text-center mb-16">
              <h1 className="font-display text-4xl font-semibold tracking-tight text-primary mb-4">
                Start free. Scale when you need to.
              </h1>
              <p className="text-secondary text-base max-w-xl mx-auto">
                Every plan includes the full gateway: identity, per-tool permissions,
                secrets vault, caching, and a complete audit log. No credit card required.
              </p>
            </div>
            <PricingTiers />
          </div>
        </section>

        <ComparisonTable />
        <BillingFAQ />

        {/* Footer links */}
        <div className="max-w-4xl mx-auto px-6 py-10 border-t border-border flex flex-wrap items-center gap-4 text-xs text-muted">
          <Link to="/docs" className="hover:text-secondary transition-colors">API Docs</Link>
          <span>·</span>
          <Link to="/security" className="hover:text-secondary transition-colors">Security</Link>
          <span>·</span>
          <Link to="/privacy" className="hover:text-secondary transition-colors">Privacy Policy</Link>
          <span>·</span>
          <Link to="/terms" className="hover:text-secondary transition-colors">Terms of Service</Link>
          <span>·</span>
          <Link to="/" className="hover:text-secondary transition-colors">Back to Arbiter</Link>
        </div>
      </main>
    </div>
  )
}

export default Pricing
