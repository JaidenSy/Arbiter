# Contributing to Arbiter

Thanks for your interest in improving Arbiter. This guide covers how to contribute and the
licensing terms that contributions are made under.

## TL;DR

- PRs are welcome. For anything non-trivial, **open an issue first** to discuss scope.
- All contributors must agree to the **Contributor License Agreement** ([CLA.md](./CLA.md)) — this is
  a one-time, one-click step handled automatically by a bot on your first PR.
- Contributions land in the **Apache-2.0 core**. The enterprise modules (SSO enforcement, SCIM, KMS)
  are not part of the open repo — see [Open-core boundary](#open-core-boundary) below.

## Open-core boundary

Arbiter is open-core. Knowing which side of the line you're contributing to avoids surprises:

- **The core gateway is Apache-2.0** and lives in this repo — the proxy pipeline, per-tool RBAC, the
  encrypted vault, semantic cache, audit logging, and the basic SSO login (Google / GitHub / OIDC).
  This is free, forever. Contributions here are welcome and are what this guide covers.
- **The enterprise modules are commercial and are *not* in this repo** — org-level SSO *enforcement*,
  SCIM provisioning, and external KMS integration. See [COMMERCIAL_LICENSE.md](./COMMERCIAL_LICENSE.md).
  They are maintained separately and are not open to outside contribution.

If you're unsure where a proposed change belongs, open an issue and we'll sort it out before you
write code.

## Development setup

```bash
git clone https://github.com/JaidenSy/Arbiter.git && cd Arbiter

# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && alembic upgrade head
uvicorn app.main:app --reload --port 8000

# frontend (separate terminal)
cd frontend && pnpm install
cp .env.example .env.local && pnpm dev

# tests
cd backend && pytest
```

## Pull request guidelines

- Branch off `develop`. PRs target `develop`, never `main` directly.
- Keep PRs focused — one logical change per PR. Small PRs get reviewed faster.
- Include tests for new behavior. Backend changes that touch the proxy, RBAC, vault, or cache paths
  should have unit coverage; raw SQL needs at least one route-level test.
- Run `ruff` and `pytest` locally before pushing.
- Describe **what** changed and **why** in the PR body. Link the issue you opened.

## Licensing of your contributions (the CLA)

By submitting a contribution you agree to the [Contributor License Agreement](./CLA.md). In short, you
keep ownership of your work and grant the project a broad license to use, modify, distribute, **and
relicense** it. The relicensing grant is deliberate: it keeps the project's licensing flexible (for
example, moving the core to a source-available license in the future) without having to track down
every past contributor. Your contribution to the Apache-2.0 core remains available under Apache-2.0.

A bot (CLA Assistant) will ask you to agree on your first PR — it's a single click against your
GitHub account and you'll never be asked again.

## Reporting security issues

Do **not** open a public issue for security vulnerabilities. Email **jaidensy07@gmail.com** with
details and we'll coordinate a fix and disclosure. See **[SECURITY.md](./SECURITY.md)** for the
full policy, scope, and what to expect.

## Questions

Open a GitHub Discussion or issue, or email **jaidensy07@gmail.com**.
