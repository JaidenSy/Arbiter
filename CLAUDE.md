# Arbiter — Repo Instructions

Self-hosted MCP gateway. Python/FastAPI backend + React/TS frontend.

## Status (2026-08-06)
`main`@`da43f60` (PR #299, 2026-07-24). **`develop` is AHEAD of `main` and none of it is on prod** — the doc fixes below plus the July Vercel-analytics commits. Shipping needs a `develop` → `main` PR. Code has been quiet since 07-24; that's low-maintenance mode, not neglect.

🟡 **PR #290 is still OPEN** (`fix/self-host-first-run` → `develop`, since 2026-06-22): docs-only README +3/−1, adds the post-`docker compose up` first-run steps and links `SECURITY.md`. Every claim re-verified against the repo 2026-08-05 and still true. ⚠️ **It was NOT blocked** — `license/cla` is a *pending*, not a *required*, check; #300 and #301 both merged with it pending. Nothing has gated #290 except no one merging it.

🔴 Business side is **spiralling** — 1★ / 0 inbound; the bottleneck is offer/ICP, not reach. Full state → RaphBrain `Projects/Arbiter/Progress.md`.

## Design artifacts — read before any UI work
`PRODUCT.md` (Impeccable schema 1) and `DESIGN.md` are the durable design record and both are machine-read by the Impeccable skill. `DESIGN.md` uses the parser's fixed section names (Overview, Colors, Typography, Layout, Elevation, Components, Do's and Don'ts) and bullet format — **renaming a heading or moving tokens back into code fences silently blinds the parser.**

🔴 **Zero customers.** No testimonials, case studies, named users, or logo walls exist. Latency figures (~1ms hash, ~10ms embed) are measured locally and may be cited as benchmarks; the "30% cache hit → 30% cost reduction" claim is **modeled, not observed.** The `use-cases.md` personas are illustrative — never convert them into case studies.

🔴 **`PLAN_LIMITS` in `backend/app/services/plan/plan_limits.py` is the source of truth for tiers.** Only `free`/`pro`/`enterprise` exist; the "Team" tier was removed from the docs 2026-08-05. Check any limit against that file before quoting it.

## Knowledge graph
`graphify-out/` holds a 3,169-node graph of this repo (gitignored, built 2026-07-29). **Ask questions about the codebase from this directory and the graphify skill answers from the graph** — ~34x cheaper than reading files. Refresh with `/graphify . --update` after significant changes. See RaphBrain `Projects/Graphify/Progress.md`.

## Start here
- Full context + current state: `~/Documents/RaphBrain/Projects/Arbiter/CONTEXT.md`, then `Progress.md`.

## Rules
- Use **pnpm**, never npm.
- Deploy: `main` → prod, `develop` → staging. Flow is `feature/*` → `develop` → `main`.
- Work off feature branches; open a PR and wait for Jaiden's review before merging.
- Never stack PRs — cut every branch from an up-to-date `main`/`develop`.

## Doc inconsistencies — RESOLVED 2026-08-05 (PR #301)
Both items the graph surfaced on 07-29 are fixed, along with two more found while verifying them. Kept here as the standing rule they taught:

- `tools/list` advertises **every** tool; RBAC is enforced **at call time**. `solution.md` claimed names were hidden and was the outlier.
- Free-tier limits now match `PLAN_LIMITS` (2 agents / 3 servers / 5,000 calls / exact-match cache). `pricing.md` had been wrong on all four; `llms.txt` was right all along.
- The phantom "Team" tier ($99/mo) and a wrong Pro vault number (500 vs 100) were also removed.

> **The rule:** resolve doc disagreements against the **code**, never by picking a file. Two of these promised more than the product delivers, which would have blocked free users at the 3rd agent and 4th server.
