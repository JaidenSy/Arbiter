# Security Policy

## Supported versions

Arbiter is pre-1.0 and under active development. Security fixes are applied to the latest
`main` — there are no long-term support branches yet. If you self-host, track `main` (or a
recent release) to receive fixes.

| Version | Supported |
| ------- | --------- |
| latest `main` | ✅ |
| older commits / forks | ❌ |

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.** Public disclosure
before a fix is available puts every self-hosted deployment at risk.

Instead, email **jaidensy07@gmail.com** with `Arbiter security` in the subject line, and include:

- A description of the vulnerability and its impact.
- Steps to reproduce, ideally with a proof-of-concept.
- The affected component (proxy, RBAC, vault, cache, auth, MCP endpoint, etc.) and the
  commit or version you tested against.
- Any suggested remediation, if you have one.

## What to expect

Arbiter is maintained by a single developer, so timelines are best-effort rather than a
contractual SLA. As a rough guide:

- **Acknowledgement** within 3 business days.
- **Initial assessment** (confirmed or not, plus severity) within 7 business days.
- A fix timeline communicated once the issue is triaged. Critical issues jump the queue.

Please allow a reasonable window to ship a fix before any public disclosure. You'll be kept
updated throughout, and credited in the advisory or release notes unless you ask not to be.

## Scope

This policy covers the **Apache-2.0 core gateway** in this repository — the proxy pipeline,
per-tool RBAC, the encrypted secrets vault, semantic cache, audit logging, and authentication
(including the basic SSO login).

The commercial enterprise modules (SSO enforcement, SCIM, KMS) are maintained separately and
are not part of this repository — see [COMMERCIAL_LICENSE.md](./COMMERCIAL_LICENSE.md). Report
issues in those by email the same way.

### Generally out of scope

To save everyone time, the following are usually **not** treated as vulnerabilities unless you
can demonstrate real impact:

- Findings that require root or an already-compromised host.
- Missing security headers on a deployment you control and configure yourself.
- Rate-limiting or brute-force concerns on endpoints sitting behind your own network controls.
- Dependency CVEs with no demonstrated exploit path in Arbiter — still worth reporting, but
  these are triaged alongside the upstream advisory.

## Disclosure

Arbiter follows coordinated disclosure: a fix is prepared and released, self-hosters get a
window to upgrade, then details are published in a GitHub Security Advisory. If you reported
the issue, you'll be credited unless you prefer to stay anonymous.
