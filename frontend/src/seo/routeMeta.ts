/**
 * Central per-route SEO metadata for the client-rendered SPA.
 *
 * Every route otherwise inherits the static <head> from index.html, so each
 * public page ends up with the homepage's title/description. This map gives
 * each route unique metadata and marks app/auth routes noindex.
 *
 * NOTE: <RouteMeta> injects this client-side. Googlebot renders it; no-JS AI
 * crawlers (GPTBot, ClaudeBot, PerplexityBot) do NOT. Full coverage for those
 * requires SSR/prerendering (tracked separately).
 */

export const SITE_URL = 'https://arbiterai.dev'

export interface PageMeta {
  title: string
  description: string
}

export const DEFAULT_META: PageMeta = {
  title:
    'Arbiter: MCP Gateway for AI Agents | Tool Access Control & Observability',
  description:
    'Arbiter is a developer-first MCP gateway for AI agents. Control which tools your agents can call, store secrets, cache responses, and observe every session — all in one place.',
}

/** Public, indexable routes with unique metadata. */
export const PAGE_META: Record<string, PageMeta> = {
  '/': DEFAULT_META,
  '/pricing': {
    title: 'Pricing: Arbiter MCP Gateway',
    description:
      'Arbiter pricing: a free tier with 5,000 tool calls/month and Pro at $29/mo for 100,000 calls. Per-tool RBAC, an encrypted secrets vault, semantic caching, and full audit logging.',
  },
  '/docs': {
    title: 'Docs & API Reference: Arbiter',
    description:
      'Arbiter API documentation: register agents, grant per-tool permissions, store vault secrets, route MCP tool calls through the gateway, and trace every session.',
  },
  '/security': {
    title: 'Security: Arbiter MCP Gateway',
    description:
      'How Arbiter secures AI agent tool access: an AES-256-GCM secrets vault, scoped agent identities, per-tool RBAC, and a complete audit log of every tool call.',
  },
  '/changelog': {
    title: 'Changelog: Arbiter',
    description:
      'New features, improvements, and fixes in Arbiter, the self-hosted MCP gateway for AI agents.',
  },
  '/privacy': {
    title: 'Privacy Policy: Arbiter',
    description: 'How Arbiter collects, uses, stores, and protects your data.',
  },
  '/terms': {
    title: 'Terms of Service: Arbiter',
    description: 'The terms that govern your use of Arbiter.',
  },

  // Authenticated app shell — noindex (see NOINDEX_PATHS), but still titled so
  // the browser tab, history entries, and screen readers can tell pages apart.
  '/agents': {
    title: 'Agents · Arbiter',
    description: 'Register and manage scoped agent identities and their API keys.',
  },
  '/mcp-servers': {
    title: 'MCP Servers · Arbiter',
    description: 'Connect and manage the MCP servers Arbiter proxies tool calls to.',
  },
  '/sessions': {
    title: 'Sessions · Arbiter',
    description: 'Audit log of agent sessions and the tool calls they make.',
  },
  '/permissions': {
    title: 'Permissions · Arbiter',
    description: 'Grant and revoke per-agent, per-tool access.',
  },
  '/vault': {
    title: 'Vault · Arbiter',
    description: 'Encrypted per-agent secrets (AES-256-GCM) injected into tool calls.',
  },
  '/settings': {
    title: 'Settings · Arbiter',
    description: 'Gateway URL, API keys, and workspace settings.',
  },
  '/account': {
    title: 'Account · Arbiter',
    description: 'Manage your profile, security, and account settings.',
  },
  '/organization': {
    title: 'Organization · Arbiter',
    description: 'Manage members and roles in your organization.',
  },
  '/webhooks': {
    title: 'Webhooks · Arbiter',
    description: 'Configure webhook endpoints for Arbiter events.',
  },
}

/**
 * Routes that must NOT be indexed: authentication flows, transactional pages,
 * and the authenticated app shell (which crawlers can't reach anyway).
 */
export const NOINDEX_PATHS = new Set<string>([
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/verify-email',
  '/confirm-email-change',
  '/accept-invite',
  '/auth/callback',
  '/cli-auth',
  '/consent',
  '/agents',
  '/mcp-servers',
  '/sessions',
  '/settings',
  '/permissions',
  '/vault',
  '/account',
  '/organization',
  '/webhooks',
])

/** Prefixes whose sub-paths are also noindex (e.g. /sessions/:id). */
export const NOINDEX_PREFIXES = ['/sessions/']
