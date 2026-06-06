# Changelog

All notable changes to Arbiter are documented here.

## [0.3.1] — 2026-06-06

### Fixed
- **Proxy tools-list now works with auth-protected MCP servers** — `POST /proxy/tools-list` was sending only `Content-Type`/`Accept` headers to upstream servers, causing silent 401s on any server that requires authentication (e.g. `Authorization: {{vault:API_KEY}}`). Vault-referenced headers are now resolved before the upstream request, matching the behaviour of `POST /proxy/tool-call`.
- **SSE streaming no longer drops events** — the proxy was breaking on the first `data:` event in a Server-Sent Events stream, silently discarding all subsequent events from multi-event responses. All events are now collected and the last valid JSON-RPC result is returned.

### Security
- **MCP server headers masked in list API** — `GET /mcp-servers` previously returned all header values verbatim, including any raw API keys pasted directly into the header field instead of using vault placeholders. Values that are not `{{vault:SECRET}}` references are now returned as `***`. Use the vault for secrets.
- **Rate limiting no longer bypassable via spoofed X-Forwarded-For** — all 9 IP-based rate limits (login, register, CLI device flow, health endpoints) previously extracted `X-Forwarded-For.split(",")[0]`, which an attacker could set to any value. The correct IP is now derived from the rightmost entry added by the trusted reverse proxy (configurable via `TRUSTED_PROXY_COUNT`, default `1` for Railway).

## [0.3.0] — 2026-06-05

### Added
- **`@arbiterai/cli` v0.1.0** — OAuth device flow CLI published to npm. Supports `login`, `logout`, `status`, `agent create/list/delete`, `permissions grant/list`, and `vault set`. Install with `npm install -g @arbiterai/cli`.
- **CLI device auth page** — `/cli-auth?code=WORD-NNNN` lets users approve or deny a CLI session from the browser without sharing credentials.
- **Landing page CLI terminal** — the CTA section now shows the full `arbiter` CLI setup flow with a CLI / Config tab switcher so users who prefer the direct MCP config can still access it.
- **FeatureShowcase Step 1** updated to show the real `arbiter agent create` CLI command.

### Fixed
- **Agent plan cap** — deactivated agents no longer count against the org's active agent limit. Deactivated agent names can be reused immediately.
- **Agent count cache** — agent count in the Dashboard and UsageStrip updates immediately after create or deactivate without requiring a manual refresh.
- **Login redirect** — unauthenticated users who visit `/cli-auth` are now correctly redirected back to the CLI auth page after logging in, instead of landing on the dashboard.

### Security
- Redis-backed rate limiting added to all three CLI auth endpoints: `POST /auth/cli/device` (10 req/min), `POST /auth/cli/token` (20 req/min), `PATCH /auth/cli/device/{code}/approve` (10 req/min).
- `user_code` wordlist expanded from 10 → 76 words, growing the namespace from ~90K to ~684K combinations.

## [0.2.1] — 2026-06-03

### Added
- **Docs tab in dashboard sidebar** — logged-in users can now navigate directly to `/docs` from the sidebar without going back to the landing page. Also included in the product walkthrough tour.

### Fixed
- **Gateway URL now defaults to the correct production URL** — the Gateway URL field in Settings previously defaulted to `http://localhost:8000/api/v1`, implying users needed to run Arbiter locally. It now defaults to the live Railway backend URL. The field also now correctly drives where the dashboard sends API requests (changing it and saving takes effect on reload).

## [0.2.0] — 2026-05-30

### Added
- Privacy policy live at `/privacy`, linked from signup and all footers
- Accessibility: skip-nav link, `eslint-plugin-jsx-a11y` enabled
- Copyright headers on core backend files

### Fixed
- Free tier MCP server count corrected on landing page (5 → 3)
- CI: upgraded to Node 22, pinned pnpm to v9 via action-setup
- Self-hosted tier gating — available to all plans, not Enterprise-only

## [0.1.0] — Initial release

- MCP gateway with agent identity and scoped API keys
- Tool-level access control (permissions) per agent
- Encrypted secrets vault
- Semantic caching
- Full agent chain observability (sessions + traces)
- Multi-tenant org support with role-based access
- Stripe billing integration (Free / Pro / Enterprise)
- Google and GitHub OAuth
