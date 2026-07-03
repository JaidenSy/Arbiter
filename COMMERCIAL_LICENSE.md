# Arbiter Enterprise Commercial License

Copyright 2026 Jaiden Sy. All rights reserved.

## Open-Core Model

Arbiter uses an open-core licensing model:

- **Core gateway — [Apache License 2.0](./LICENSE)** — free, permissive, self-hostable. Use it, modify
  it, build on it, embed it in proprietary products. No copyleft obligations.

- **Enterprise modules — Commercial License required** — a separate commercial license is required
  to use the enterprise modules: **SSO enforcement, SCIM, and KMS**. These modules are not included
  in the Apache-2.0 core distribution.

> **Note:** the individual SSO *login* (Google / GitHub / OIDC sign-in) that ships in the core is
> **free and Apache-2.0** — it is not an enterprise module. The commercial line is org-level **SSO
> *enforcement*** (requiring all members to authenticate via your IdP), not the ability to log in with SSO.

---

## What requires a commercial license

A commercial license is required only if you are using the **enterprise modules**:

- **SSO enforcement** — org-level SAML/SSO *requirement* (force all members through your IdP). The basic SSO login is free in the core.
- **SCIM** — automated user provisioning and de-provisioning
- **KMS** — external key management service integration (AWS KMS, GCP Cloud KMS, HashiCorp Vault)

You do **not** need a commercial license for:

- Using, modifying, or distributing the core Arbiter gateway (Apache-2.0 covers all of this).
- Building proprietary products or SaaS on top of the core gateway.
- Self-hosting the core gateway internally or for customers.
- The individual SSO login (Google / GitHub / OIDC sign-in) — that ships in the core, free.
- Evaluating Arbiter for any purpose.

---

## Purchasing a commercial license

Contact: **jaidensy07@gmail.com**

Include in your message:

- Company name and size (number of engineers / seats)
- Which enterprise module(s) you need (SSO enforcement, SCIM, KMS)
- Whether you need a single-deployment or multi-deployment license

Pricing is negotiated per engagement.

---

## What a commercial license grants you

- The right to use the licensed enterprise module(s) in production.
- The right to embed enterprise modules in a closed-source product or hosted service.
- Access to priority support and a private Slack channel (Enterprise tier).
- A named invoice suitable for your legal / procurement team.

---

## No Warranty

Arbiter and its enterprise modules are provided "as is", without warranty of any kind.
The author is not liable for any damages arising from use of this software.
