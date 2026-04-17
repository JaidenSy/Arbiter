# Comparison

NexVault is not the only tool in this space. Here is an honest assessment of the alternatives — where they are strong, where they fall short, and when NexVault is (and is not) the right choice.

---

## vs LiteLLM

**What LiteLLM is good at**: LLM routing. If you need to proxy requests across 100+ LLM providers, handle fallbacks, enforce per-key spend limits, and route by model cost or latency — LiteLLM is excellent. It is mature, battle-tested, MIT licensed, and free to self-host.

**Where it falls short for MCP agent infrastructure**:

- **No encrypted secrets vault.** LiteLLM stores OAuth client credentials in config files. There is no AES-encrypted per-agent secret store with runtime injection.
- **No per-agent API key identity.** LiteLLM uses "virtual keys" but they are generic API keys, not first-class agent identity artifacts with a `nxai_`-style prefix, SHA-256-only storage, and per-agent scoping.
- **No tool call semantic cache.** LiteLLM caches LLM completions. MCP tool call results — file reads, database queries, search results — are not cached. NexVault caches at the tool response layer.
- **RBAC requires Enterprise ($250/month).** Free and open-source tiers have no RBAC. SSO and audit logs are also Enterprise-only.
- **`tools/list` not filtered by RBAC.** Tools not granted to an agent are still returned in `tools/list` — agents can enumerate capabilities they cannot use.
- **Security incident in 2025.** LiteLLM's npm package ecosystem was compromised in a supply chain attack. The Python package was not directly affected, but it highlighted the project's attack surface.

LiteLLM MCP support was added in late 2025 and is improving, but it is LLM-first tooling with MCP bolted on. NexVault is MCP-first.

**When to use LiteLLM over NexVault**: You need multi-provider LLM routing, spend tracking across model providers, or you're doing prompt caching across OpenAI/Anthropic/Gemini. NexVault does not do any of that.

---

## vs Portkey

**What Portkey is good at**: Managed AI gateway with strong LLM observability. Routes to 250+ providers, has a polished UI for prompt management and traces, semantic caching for LLM completions, and as of March 24, 2026, the core gateway is fully open-sourced.

**Where it falls short**:

- **No encrypted secrets vault.** Portkey manages upstream MCP server credentials at the platform level, but there is no AES-encrypted per-agent secret store. Credentials are not cryptographically scoped per-agent with `{{SECRET_NAME}}` injection at runtime.
- **Semantic cache is for LLM completions, not tool calls.** Portkey caches the LLM response layer. NexVault caches what the MCP server returned — file contents, query results, search hits. These are different things.
- **Agent identity is workspace-scoped, not agent-scoped.** Portkey service account keys are not per-agent identity artifacts. There is no per-agent API key with isolated permissions and an isolated vault namespace.
- **MCP support was added late 2025** — Portkey is an LLM gateway that added MCP. The architecture is LLM-first.
- **Enterprise features require custom pricing.** RBAC, SSO, VPC deployment, and HIPAA compliance are not self-serve. Free and Production tiers ($49/mo) do not include VPC or SSO.
- **Open-sourcing (March 2026) creates self-hosted competition.** Portkey's self-hosted gateway is now free. But it still lacks an encrypted vault and MCP tool call caching, and it's a more complex deployment than a single Docker Compose.

**When to use Portkey over NexVault**: You want a managed SaaS LLM gateway with a polished trace UI across Claude, GPT-4, Gemini, and you don't need per-agent encrypted credentials or MCP tool call caching. Portkey's $49/month tier is a good value for LLM-layer observability.

---

## vs Kong AI Gateway

**What Kong is good at**: Enterprise API management at scale. If you have 50+ services, a dedicated platform engineering team, and a Kubernetes cluster, Kong handles API gateway concerns (auth, rate limiting, load balancing, analytics) extremely well. Kong's MCP proxy, added in 2025–2026, extends these capabilities to AI agent traffic.

**Where it falls short for most AI teams**:

- **Minimum spend is $2,500/month** for the base API management platform. AI agent management (LLM proxy, MCP proxy, A2A proxy) and enterprise auth (OAuth/OpenFGA) are separate line items. All-in cost for MCP governance: $5,000–$20,000+/month.
- **No built-in encrypted secrets vault.** Kong delegates credential storage to external systems — HashiCorp Vault, AWS Secrets Manager — which adds operational complexity.
- **Requires Kubernetes expertise.** Not `docker compose up` friendly. A typical Kong deployment involves Helm charts, ingress controllers, and persistent volume configuration.
- **Agent identity is OAuth-scoped**, tied to enterprise IdP (Okta, Entra). There is no lightweight API key system for programmatic agent clients.
- **MCP semantic cache is for LLM tokens**, not tool call results.

**When to use Kong over NexVault**: You are a large enterprise with an existing Kong deployment, a Kubernetes infrastructure team, and $5,000+/month API management budget. NexVault is explicitly not competing at this price point and complexity level.

---

## vs Gravitee

Gravitee is in the same category as Kong: enterprise API management platform with MCP proxy added in v4.9 (late 2025). RBAC 2.0, OAuth scope-per-tool, A2A proxy. Pricing starts at $2,500/month for the base platform, with AI agent management as a separate add-on.

The same tradeoffs apply: powerful for large enterprise teams with infra expertise, inaccessible for developers, startups, and small teams. No built-in encrypted secrets vault, no per-agent lightweight API keys, no self-serve free tier.

---

## vs DIY

DIY is the most common alternative. Most teams build this incrementally — a few env vars here, a home-grown permission check there — until they have a fragile, undocumented auth system that no one fully understands.

The honest cost of doing this right:

| Component | Senior engineer time |
|-----------|---------------------|
| Agent identity + key management | 3–5 days |
| AES-256-GCM vault with nonce handling | 3–4 days |
| Per-tool RBAC (wildcard, indexed query) | 2–3 days |
| Gapless audit log (all outcomes, not just success) | 1–2 days |
| 3-layer semantic cache (Redis + Postgres + embeddings) | 1–2 weeks |
| **Total** | **3–4 weeks** |

That's engineering time at $75–150/hour = $36,000–$96,000 in labor, plus ongoing maintenance. A security review of a DIY vault implementation at an enterprise is typically $15,000–$40,000 separately.

NexVault on the free tier costs $0. On Pro it costs $29/month. The math is not close.

The counterargument for DIY: you own the code, you understand every decision, there is no dependency on an external project. That is a legitimate concern. NexVault is MIT licensed and self-hostable — you can fork it, audit it, and never depend on the hosted version.

---

## Summary

| | NexVault | LiteLLM | Portkey | Kong/Gravitee | DIY |
|---|---|---|---|---|---|
| MCP-native | Yes | Partial | Partial | Partial | N/A |
| Per-agent encrypted vault | Yes | No | No | No (external) | You build it |
| Per-agent API key identity | Yes | No | No | No | You build it |
| Tool call semantic cache | Yes | No | No | No | You build it |
| RBAC (free/affordable) | Yes | $250/mo | $49/mo (partial) | $2,500+/mo | You build it |
| Gapless audit log | Yes | Enterprise | Partial | Yes | You build it |
| Single Docker Compose | Yes | Yes | Complex | No | N/A |
| Price floor | $0 | $0 | $0 | $2,500/mo | Labor cost |

NexVault's defensible position: the only MCP-native gateway with all four differentiators — per-agent encrypted vault, per-agent API key identity, tool call semantic cache, and single `docker compose up` deployment — at a price accessible to individual developers and small teams.
