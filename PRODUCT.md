# Product

<!-- impeccable:product-schema 1 -->

## Product Name
ArbiterAI (formerly NexVault)

## Platform

web

## Users
Developers and small engineering teams building AI agent systems. They:
- Write code daily, have strong opinions about tools
- Distrust marketing language immediately
- Evaluate products by reading the UI, not the copy
- Compare against Linear, Stripe Dashboard, Raycast — tools that disappear into the task
- Will leave if onboarding feels hand-holdy or the UI feels unfinished

Secondary: technical founders evaluating security/compliance posture before adopting.

## Product Purpose
MCP security gateway: every tool call from AI agents goes through Arbiter before reaching the server. Arbiter logs it, caches it, and enforces the permissions you set. Observable, auditable, controllable AI agent infrastructure.

## Positioning

**Agent identity and tool authorization.** Every agent gets its own key, permission is enforced at call time, and the audit log is gapless. Arbiter is the auth and identity layer that AI tooling is missing.

The neighbouring products are LLM proxies that bolted MCP on afterwards: LiteLLM, Portkey, and Kong are all only partial on MCP, and none of them has per-agent API keys, an encrypted credential vault, or tool-call-level RBAC. Identity is the axis they cannot copy without rebuilding around tool calls.

> `tools/list` advertises every tool in the org. Permission is enforced **at call time**, not by hiding names from discovery. Never describe the model the other way round — it overstates the security posture, and a technical evaluator will test it.

## Operating Context

**Self-host first; hosted is the convenience path.** The `docker compose up` install is the main way in, and `arbiterai.dev` is the secondary. Design and docs work optimizes for first run, configuration, and the self-hosted path before it optimizes for signup funnel.

- Self-hosting brings up the frontend on `:3000` and the API on `:8000`; the container runs `alembic upgrade head` on start.
- First account is created at the frontend, gated by `ALLOW_PUBLIC_REGISTRATION` or `INVITE_CODE`.
- Self-hosted deployments do not report usage. Free is honour-system; Pro self-hosted uses a licence key.
- Evaluators arrive skeptical and read the UI and the docs before the copy. The repo itself is part of the product surface.

## Capabilities and Constraints

- Python/FastAPI backend, React/TypeScript frontend, PostgreSQL, Redis. Deploys as a single Docker Compose stack.
- **Use pnpm, never npm.**
- Enforced plan limits live in `backend/app/services/plan/plan_limits.py` and are the single source of truth. Free: 2 agents, 3 MCP servers, 5,000 tool calls/mo, 10 vault secrets, exact-match cache only. Pro: 25 / 50 / 100,000 / 100, semantic cache on. Enterprise: unlimited.
- **Only three tiers exist** — `free`, `pro`, `enterprise`. Any doc describing a "Team" tier is stale; it was removed 2026-08-05.
- The semantic cache is deliberately off for free orgs, to keep the embedding model out of RAM.
- **Undecided:** whether a Team tier ships at all. Do not reintroduce it in copy before it exists in `PLAN_LIMITS`.

## Brand Commitments

- Direct and specific. "Every call is logged" not "gain full visibility into your AI workflows."
- Use the technical vocabulary users already have: MCP, tool call, proxy, agent, secret.
- Write like a senior engineer explaining a system to a peer, not a marketer writing for a demo.
- Credibility through specificity — concrete numbers, real status codes, actual key formats.
- **No em dashes in UI copy** (use colons, commas, semicolons). No emoji anywhere in the UI.
- Agent API keys carry the legacy `nxai_` prefix from the NexVault name. It is load-bearing in existing installs; do not "clean it up" in copy or code without a migration.

### Anti-references
- Generic SaaS purple/blue gradients and floating orbs (vibecoded)
- "Empower / unleash / revolutionize / supercharge" copy
- Identical icon-card feature grids with vague headings
- Fake testimonials or fake metric counters
- Landing pages that could be for any B2B SaaS product
- Over-animated page loads or hero sequences

## Evidence on Hand

Real and citable:
- The product is live and self-hostable; `arbiterai.dev` is running.
- **Latency figures are measured locally** and may be stated as benchmarks with that caveat: ~1ms for the SHA-256 canonical-params hash, ~10ms for the FastEmbed `all-MiniLM-L6-v2` ONNX embedding, 10–15ms CPU on the event path.
- The competitor comparison in `docs/pitch/comparison.md` is built from published competitor pricing and feature pages.

Absences that future work must **not** fabricate around:
- **Zero customers.** No testimonials, no case studies, no named users, no logo wall, no star counts, no "trusted by" line. None of these exist.
- **The cost and cache-rate claims are modeled, not observed.** "30% cache hit rate → roughly 30% cost reduction" is a design estimate. Never present it as production-proven.
- The personas in `docs/pitch/use-cases.md` are illustrative, not real accounts. Do not convert them into case studies.

## Product Principles

1. **Show, don't tell.** Real session traces beat feature lists. Real key formats beat security claims.
2. **Credibility before conversion.** A developer must trust the product before they sign up. The UI should feel more finished than it needs to be.
3. **No buzzwords, ever.** If a word could appear on a VC pitch deck, replace it with the actual thing it describes.
4. **The app disappears into the task.** Users are in flow. UI is infrastructure, not theater.
5. **Dark by default.** Developers at 2am. Don't make them squint.
6. **Docs claims must match enforced behaviour.** The code is the source of truth for limits and for the security model. Four pitch-doc contradictions shipped for weeks because nobody checked against `PLAN_LIMITS` and `mcp.py`.

## Accessibility & Inclusion

**ADA (US) and the EAA (EU, enforced June 2025) apply** — a B2B developer tool is lower risk than a consumer app, but not zero, and enterprise or government pursuit raises it immediately.

In place today: a skip-to-main-content link (`App.tsx`), and `eslint-plugin-jsx-a11y` wired into `eslint.config.js` so violations surface as lint warnings.

Known open gaps, not yet closed: label association across ~24 files, unlabeled icon-only controls, a click handler on a non-interactive element, `autoFocus` usage, no focus trap or focus return on modal close, and no automated a11y regression testing (`@axe-core/playwright` is still absent — verified 2026-08-06).

**Undecided:** no conformance target has been set. Do not assert WCAG 2.1 AA (or any level) until it is chosen and verified.
