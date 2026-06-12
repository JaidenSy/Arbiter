/**
 * Arbiter — Plan tier data shared by the landing page pricing section and
 * the dedicated /pricing page.
 *
 * Tier limits mirror the backend PLAN_LIMITS table
 * (backend/app/services/plan/plan_limits.py) — update both together.
 */

export const SUPPORT_EMAIL: string =
  (import.meta.env.VITE_SUPPORT_EMAIL as string | undefined) ?? 'support@arbiterai.dev'

export interface PricingTier {
  name: string
  price: string
  period?: string
  features: string[]
  cta: string
  ctaHref: string
  highlighted?: boolean
}

export const pricingTiers: PricingTier[] = [
  {
    name: 'Free',
    price: '$0',
    period: '/mo',
    features: [
      '2 agents',
      '3 MCP servers',
      '5,000 tool calls/mo',
      '10 vault secrets',
      'Exact-match caching',
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
      'Semantic caching',
      'Cost tracking & anomaly detection',
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
