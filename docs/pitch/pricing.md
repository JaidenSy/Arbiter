# Pricing

## Tiers

| | Free | Pro | Team | Enterprise |
|---|---|---|---|---|
| **Price** | $0/mo | $29/mo | $99/mo | Custom |
| **Agents** | 3 | 25 | Unlimited | Unlimited |
| **MCP servers** | 5 | 50 | Unlimited | Unlimited |
| **Tool calls/month** | 1,000 | 100,000 | 1,000,000 | Unlimited |
| **Vault secrets** | 10 | 500 | Unlimited | Unlimited |
| **Audit log retention** | 7 days | 30 days | 90 days | Custom |
| **Semantic cache** | Yes | Yes | Yes | Yes |
| **RBAC** | Yes | Yes | Yes | Yes |
| **Self-hosted** | Yes | Yes | Yes | Yes |
| **Priority support** | No | No | Yes | Yes |
| **SSO (Okta / Entra)** | No | No | No | Yes |
| **SLA** | No | No | No | Yes |
| **Audit log export** | No | No | No | Yes |
| **Dedicated infra** | No | No | No | Yes |

---

## Free tier

The free tier is not a crippled trial. 3 agents, 5 MCP servers, and 1,000 tool calls per month covers:

- A solo developer's personal agent setup
- A team evaluating NexusAI before committing
- An open source project with a small number of automated agents
- A student or hobbyist building agent tooling

The free tier includes the full feature set — semantic cache, RBAC, encrypted vault, audit log. The only limits are volume-based.

There is no time limit on the free tier. You do not get downgraded after 14 or 30 days.

---

## Why the semantic cache makes Pro ($29/mo) pay for itself

At scale, you are making repeated or near-duplicate tool calls. The semantic cache eliminates those redundant upstream calls.

**Example scenario: Pro tier, 100,000 tool calls/month**

| | Without cache | With cache (30% hit rate) |
|---|---|---|
| Upstream calls made | 100,000 | 70,000 |
| Calls saved | 0 | 30,000 |
| Cost saved at $0.01/call avg | $0 | $300/month |
| NexusAI Pro cost | — | $29/month |
| **Net savings** | — | **$271/month** |

30% is a conservative hit rate for typical agent workloads. Agents running similar queries repeatedly — file reads, database lookups, search queries — commonly hit 40–60%.

The Pro tier costs $29/month. The cache pays for itself at roughly 3,000 avoided upstream calls per month.

---

## Comparison

| | NexusAI Free | NexusAI Pro | NexusAI Team | LiteLLM OSS | LiteLLM Enterprise | Portkey Production | Kong AI |
|---|---|---|---|---|---|---|---|
| **Price** | $0 | $29/mo | $99/mo | $0 | $250/mo | $49/mo | $2,500+/mo |
| **MCP-native** | Yes | Yes | Yes | Partial | Partial | Partial | Add-on |
| **Encrypted vault** | Yes | Yes | Yes | No | No | No | External only |
| **Per-agent API keys** | Yes | Yes | Yes | No | No | No | No |
| **Tool call semantic cache** | Yes | Yes | Yes | No | No | No | No |
| **RBAC** | Yes | Yes | Yes | No | Yes | Yes | Yes |
| **Gapless audit log** | Yes | Yes | Yes | No | Yes | Partial | Yes |
| **Self-hosted** | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| **Single Docker Compose** | Yes | Yes | Yes | Yes | No | No | No |

LiteLLM requires the $250/month Enterprise plan for RBAC and audit logs. Portkey's $49/month plan includes RBAC but has no encrypted vault and caches LLM completions (not tool call results). Kong's entry price for AI agent features is north of $2,500/month and requires Kubernetes expertise.

---

## Enterprise

Enterprise pricing is custom and covers:

- Dedicated infrastructure (your VPC, your cloud account, or on-prem)
- SLA with defined response times
- SSO integration (Okta, Microsoft Entra, Google Workspace)
- Audit log export to SIEM (Splunk, Datadog, S3)
- SOC2 Type II documentation and security review support
- Dedicated support channel and onboarding

Enterprise is the right choice for teams with data residency requirements, SOC2 obligations, or compliance teams that need documented security controls.

[Contact us](mailto:enterprise@nexusai.dev) to discuss Enterprise pricing.

---

## Billing notes

- All plans are month-to-month. No annual commitment required.
- Tool call counts reset at the start of each billing cycle.
- Overages on the Free tier result in rate limiting (not charges).
- Overages on Pro and Team result in per-call charges at $0.0005/call above the limit, or you can upgrade tiers mid-cycle.
- Self-hosted deployments on any tier do not report usage to NexusAI servers. Honor system for Free; Pro and Team self-hosted plans use a license key.
