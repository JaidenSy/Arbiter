/**
 * Arbiter — Shared pricing tier cards.
 *
 * Single source of truth for the plan tiers, rendered on both the landing
 * page (#pricing section) and the dedicated /pricing page.  Tier limits
 * mirror the backend PLAN_LIMITS table
 * (backend/app/services/plan/plan_limits.py) — update both together.
 */

import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { RevealGroup } from './RevealGroup'
import { pricingTiers } from './pricingData'

interface PricingTiersProps {
  /** Render a "Compare all features" link under the grid (used on the landing page). */
  showCompareLink?: boolean
}

export default function PricingTiers({ showCompareLink }: PricingTiersProps): React.ReactElement {
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
    <>
      <RevealGroup className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch" stagger={80}>
        {pricingTiers.map((tier) => (
          <div
            key={tier.name}
            className={`flex flex-col rounded-2xl p-7 transition-colors duration-200 ${
              tier.highlighted
                ? 'bg-surface border border-border-accent shadow-[0_0_28px_rgba(61,53,206,0.16)]'
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
      </RevealGroup>

      {showCompareLink && (
        <div className="text-center mt-10">
          <Link
            to="/pricing"
            className="inline-flex items-center gap-2 text-accent-light hover:text-primary text-sm font-medium transition-colors"
          >
            Compare all plan features →
          </Link>
        </div>
      )}
    </>
  )
}
