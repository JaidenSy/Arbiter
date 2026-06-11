# Changelog

All notable changes to Arbiter are documented here.

## [Unreleased]

### Added
- **Native MCP endpoint** — The gateway is now itself an MCP server. Any MCP client (Claude Code, Claude Desktop, Cursor, VS Code) connects with one URL: `POST /mcp` with `Authorization: Bearer nxai_...`, or `POST /mcp/{api_key}` for clients that cannot set headers. All registered MCP servers in the org are aggregated into one virtual server with tools namespaced as `server__tool`, RBAC-filtered per agent (60s per-agent cache). Every `tools/call` runs the full gateway pipeline — RBAC, vault injection, semantic cache, quotas, budgets, audit log. Gateway denials are returned as JSON-RPC errors with the HTTP status in `error.data.http_status`. See `docs/mcp-endpoint.md`.

### Fixed
- **App could not boot on v0.4.0** — two missing imports (`ChainNode` in sessions.py, `webhooks` in main.py) crashed the API at startup; Railway silently kept serving the previous deployment.
- **SSRF re-check on tools/list** — the REST `POST /proxy/tools-list` path now re-validates the upstream URL at request time (DNS-rebinding guard), matching `tool-call` behaviour.
- Landing page now shows the real agent key format (`nxai_...`) instead of a fictional `arb_sk_...` prefix.

## [0.4.0] — 2026-06-10

### Added
- **Per-session tool-call budget** (#211) — Agents can now be assigned a `max_calls_per_session` cap. Once exceeded, the gateway returns HTTP 402 `session_budget_exceeded` with `{ session_id, used, limit }`. Agents can check their remaining budget via `GET /proxy/session-budget?session_id=...`. Cache hits are excluded from the count. Configurable in the Register and Edit agent modals.
- **Multi-hop agent chain tracing** (#210) — When an agent passes `X-Arbiter-Parent-Session-Id` on a tool call, the new session inherits a shared `trace_id`. `GET /sessions/{id}/chain` reconstructs the full call tree across any chain depth. Sessions that are part of a chain now show a collapsible `CallChainPanel` in the SessionTrace view with click-through links to parent and child sessions.
- **Webhooks** (#184) — Orgs on Pro+ can register webhook endpoints that receive HMAC-signed `POST` requests for key events: `permission.denied`, `quota.exceeded`, and `mcp_server.offline`. Delivery is attempted up to 3 times with exponential backoff. A full delivery log is available in Settings.
- **Cost tracking** (#186) — MCP servers now have an optional `cost_per_call_usd` field. When set, each tool call records its USD cost in the `SessionEvent`. Cumulative cost is exposed via `GET /stats/cost` (Pro+) and surfaced as a tile on the Dashboard.
- **MCP server health monitoring + circuit breaker** (#208) — Each registered MCP server is now periodically health-checked. Servers with repeated failures are automatically circuit-broken and marked offline. An uptime badge is shown on the MCP Servers list. The `mcp_server.offline` webhook fires on state change.
- **Latency percentiles + drill-down stats** (#185, #205) — `GET /stats` now returns p50/p95/p99 latency and a slowest-tools list. All stats endpoints accept `agent_id` and `server_id` query params for drill-down. A filter bar on the Dashboard exposes these filters.
- **Per-agent analytics** (GROWTH-01) — `GET /agents/{id}/analytics` returns call volume, error rate, and latency breakdown for a single agent over a configurable time window.
- **Quota alerts** (GROWTH-03) — Orgs approaching their monthly tool-call quota receive an email alert at 80% and 95% usage.
- **Audit log export** (GROWTH-04) — `GET /audit/export` returns a paginated CSV or JSON export of the audit log, filterable by date range.
- **Execution traces** (GROWTH-05) — `GET /traces` and `GET /traces/{id}` provide structured execution traces for individual tool calls, including latency breakdown by pipeline stage.
- **Anomaly detection** — `GET /agents/{id}/risk` (Pro+) returns a risk score and anomaly flags based on recent call patterns.
- **Retry backoff** (#181) — Tool calls that fail with a timeout or connection error are automatically retried up to 2 times with 1s → 2s exponential backoff.

### Fixed
- **JWT blocklist fails closed** (#198) — A Redis outage previously left the token blocklist unreachable, allowing revoked tokens to pass. The blocklist now fails closed by default (treats Redis unavailability as "token may be revoked"). Set `JWT_BLOCKLIST_FAIL_OPEN=true` to revert to the old behaviour.
- **DNS rebinding / SSRF guard** (#182) — The SSRF check is now performed at proxy-request time (not only at server registration) and shared via `app/core/ssrf.py`. This closes a window where a DNS rebinding attack could swap a safe hostname for a private IP after the server was registered.
- **Vault rate limit** (#192) — Vault read endpoints are now rate-limited to prevent secret enumeration.
- **RBAC cache invalidation** (#193) — Permission cache entries are now correctly evicted when a permission rule is revoked.
- **Quota deduplication** (#194) — Concurrent tool calls that raced the quota check could previously double-count usage. Deduplication via Redis ensures each call is counted exactly once.
- **Async SSRF DNS** (#195) — The synchronous `socket.getaddrinfo` call in the SSRF check blocked the event loop; replaced with async DNS resolution.
- **Vault secret auto-hide** (#180) — Revealed vault secrets now automatically re-hide after 30 seconds without requiring a manual click.
- **Date filter validation** (#187) — `from_date` / `to_date` on list and export endpoints now validates that `from_date < to_date`, returning 422 on invalid ranges.
- **CLI verification URI** (#175) — The `verification_uri` returned by `POST /auth/cli/device` is now derived from `settings.frontend_url` instead of being hardcoded to localhost.

### Security
- **JWT blocklist fails closed on Redis outage** — see Fixed above.
- **DNS rebinding SSRF guard at proxy request time** — see Fixed above.

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
