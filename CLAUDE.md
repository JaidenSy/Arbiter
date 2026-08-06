# Arbiter — Repo Instructions

Self-hosted MCP gateway. Python/FastAPI backend + React/TS frontend.

## Status (2026-08-05)
`main`@`da43f60` (PR #299, 2026-07-24); `develop` is level with `main`, nothing in flight. Code has been quiet since 07-24 — that's low-maintenance mode, not neglect.

🟡 **PR #290 is OPEN** (`fix/self-host-first-run` → `develop`, since 2026-06-22): docs-only, README +3/−1, adds the post-`docker compose up` first-run steps and links `SECURITY.md`. Verified 2026-08-05 — every claim in it still matches the repo (frontend `3000:80`, backend 8000 with `alembic upgrade head` on start, `JWT_SECRET_KEY`/`ALLOW_PUBLIC_REGISTRATION`/`INVITE_CODE` all in `.env.example`, `SECURITY.md` present), and the README still lacks both changes. **It is blocked only on the unsigned CLA** (cla-assistant); Vercel checks pass. Sign or merge it — six weeks stalled on a click.

🔴 Business side is **spiralling** — 1★ / 0 inbound; the bottleneck is offer/ICP, not reach. Full state → RaphBrain `Projects/Arbiter/Progress.md`.

## Knowledge graph
`graphify-out/` holds a 3,169-node graph of this repo (gitignored, built 2026-07-29). **Ask questions about the codebase from this directory and the graphify skill answers from the graph** — ~34x cheaper than reading files. Refresh with `/graphify . --update` after significant changes. See RaphBrain `Projects/Graphify/Progress.md`.

## Start here
- Full context + current state: `~/Documents/RaphBrain/Projects/Arbiter/CONTEXT.md`, then `Progress.md`.

## Rules
- Use **pnpm**, never npm.
- Deploy: `main` → prod, `develop` → staging. Flow is `feature/*` → `develop` → `main`.
- Work off feature branches; open a PR and wait for Jaiden's review before merging.
- Never stack PRs — cut every branch from an up-to-date `main`/`develop`.

## Known doc inconsistencies (unresolved, surfaced by the graph 2026-07-29)
- `docs/pitch/solution.md` says unpermitted tools are **hidden** from `tools/list`; `docs/rbac.md`, `docs/mcp-servers.md`, `docs/mcp-endpoint.md` all say all tools are advertised and RBAC is enforced at **call time**. Confirm which is true before quoting either to a prospect.
- Free-plan limits disagree: `frontend/public/llms.txt` = 5,000 calls / 2 agents / 3 servers vs `docs/pitch/pricing.md` = 1,000 / 3 agents / 5 servers.
