# Use Cases

Four types of people buy or adopt Arbiter. Here is who they are, what their specific problem looks like, and how Arbiter solves it.

---

## 1. Solo AI Developer

**Who they are**: Building personal agents, side projects, or open source tools. Writing Python scripts that call Claude and route tool use through MCP servers. Usually solo or with one or two collaborators.

**Their problem**:

They have API keys — GitHub, Notion, Slack, maybe a Postgres database — and those keys are in `.env` files. Some of those `.env` files have ended up in git history or in Slack messages. They have no idea what their agent actually called last Tuesday when it ran for 20 minutes and cost $3 in API fees. They want to add a second agent but don't want it to have the same level of access as the first.

They know the right thing to do is to put secrets in a vault and add access control. They don't want to spend a week building that infrastructure for a side project.

**How Arbiter solves it**:

```bash
docker compose up -d
```

Register two agents, each gets its own `nxai_` key. Store their secrets in the vault — `GITHUB_TOKEN`, `NOTION_TOKEN`. Use `{{GITHUB_TOKEN}}` in tool arguments instead of the raw value. Grant the research agent read-only file access. Grant the writer agent broader access. Check the dashboard when the 20-minute run ends and see exactly what was called and what each call returned.

The `.env` file now contains `VAULT_ENCRYPTION_KEY` and Postgres credentials — nothing specific to GitHub or Notion.

**Which tier fits**: Free. 3 agents and 5 MCP servers cover a solo developer's full setup. 1,000 tool calls/month is generous for personal use.

---

## 2. AI Startup (Series A)

**Who they are**: A team of 5–20 engineers shipping a product where AI agents call MCP tools on behalf of their customers. Each customer gets their own agent (or their own set of agents). They are starting to think about enterprise sales, which means SOC2 Type II is on the roadmap.

**Their problem**:

Their product creates an agent per customer. That agent calls MCP servers using the customer's credentials — their Salesforce token, their GitHub token, their database connection string. Right now, those tokens are stored in a Postgres `customers` table in a `credentials` JSONB column, unencrypted. There is no per-customer access control — all customer agents have the same tool permissions. An audit log query takes 20 minutes because all tool calls are just in application logs.

They are talking to a Fortune 500 prospect. The prospect's security team asks: "How do you ensure that Customer A's credentials cannot be accessed by Customer B's agent?" Current answer: "We trust the application code." That answer is not going to close the deal.

**How Arbiter solves it**:

Register one agent per customer in Arbiter. Each agent has its own `nxai_` key. Store each customer's credentials in the vault scoped to their agent — `SALESFORCE_TOKEN`, `GITHUB_PAT`. Use `{{SALESFORCE_TOKEN}}` in tool arguments. Grant each customer's agent only the tools their subscription tier permits.

Now the answer to the prospect's security team: "Customer A's credentials are AES-256-GCM encrypted, stored under a per-agent namespace, and cryptographically inaccessible to Customer B's agent. Audit logs record every tool call with full request and response payloads, retention 30 days." That closes deals.

The semantic cache also matters here: when multiple customers query similar data from a shared read-only MCP server, cache hits reduce per-customer upstream API costs. At 30% cache hit rate, costs drop by roughly 30%.

**Which tier fits**: Pro ($29/month) to start. When customer count grows past 25 agents, Team ($99/month). The math: the cache alone likely saves more than the tier cost in upstream API fees.

---

## 3. Platform / Infrastructure Engineer

**Who they are**: Running the internal developer platform at a 100–500 person company. There are 4 product teams, 20+ AI agents across various services, and the chaos is getting real. An engineer on Team A deploys an agent last month. This week someone asks: "What is that agent doing? Is it touching our production database?"

**Their problem**:

API keys for AI agents are scattered across 10 repositories in `.env` files, CI/CD secrets, and some are hardcoded in shell scripts that no one wants to touch. Three different teams have registered three different MCP servers for the same database — with different names, different configurations, and different (inconsistent) access controls. The compliance team asked for "a list of all tools that AI agents can call in production." Nobody can produce that list.

The security team is asking about secrets rotation policy. The current policy is: "we rotate when we remember." Last rotation was 14 months ago, and even then, two services missed the update.

**How Arbiter solves it**:

Deploy Arbiter as the centralized MCP gateway. All 20+ agents register through it. All MCP servers register through it. Secrets rotation now happens in one place — update the vault, the next tool call gets the new value. Permission changes for an agent happen through the Arbiter API, not by editing config files across 10 repos.

The "list of all tools agents can call" is now a single API query:

```bash
curl -s http://localhost:8000/api/v1/agents?include_permissions=true
```

The compliance report that used to take two days to compile now takes 5 minutes.

The semantic cache cuts internal infrastructure costs: if four teams' agents are all running similar database queries through a shared MCP server, L3 similarity cache hits eliminate redundant query load.

**Which tier fits**: Team ($99/month). Unlimited agents and servers, 1 million tool calls/month, 90-day audit log retention. The audit log retention matters — compliance teams typically want 90 days of tool call history.

---

## 4. Enterprise AI Team

**Who they are**: A large enterprise (500+ employees) with an AI team that is deploying agents into production workflows — document processing, data analysis, internal tooling. The company is pursuing SOC2 Type II certification. Legal has flagged that AI agents calling external tools with customer credentials needs governance controls in place before the audit.

**Their problem**:

Legal's specific requirements: (1) credentials must be encrypted at rest with documented key management, (2) access control must be documented and auditable, (3) audit logs must be gapless and exportable to the company's SIEM, (4) no third-party SaaS may hold production credentials. Requirement 4 rules out Portkey's managed offering. Requirement 3 rules out tools that only log successful calls.

Kong or Gravitee would technically meet the requirements, but the procurement and deployment timeline is 3–6 months, and the annual cost is $60,000+. The AI team needs this operational within 6 weeks.

**How Arbiter solves it**:

Self-host Arbiter inside the company's VPC. Data never leaves their infrastructure. The vault encryption (AES-256-GCM with documented key management in `Decisions.md`) is SOC2-compatible. The audit log records every outcome — success, permission denial, error, timeout — satisfying the gapless requirement. SIEM export is available at the Enterprise tier via audit log export to S3 or a webhook.

The deployment timeline is measured in days, not months. The cost is a fraction of Kong or Gravitee.

For the SOC2 audit, Arbiter provides: documented encryption decisions, a gapless audit log schema, per-agent access control that is reviewable by the auditor, and separation between the master encryption key (env var) and the encrypted data (database).

**Which tier fits**: Enterprise (custom pricing). Dedicated infra, SLA, audit log export, SSO integration, and a documented security review process. [Contact us](mailto:enterprise@arbiterai.dev) to discuss.
