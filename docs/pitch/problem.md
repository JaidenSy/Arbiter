# The Problem

Every AI team building with MCP eventually builds the same infrastructure. Most build it badly, twice.

---

## What teams actually do today

Walk through a typical AI feature launch:

**Week 1**: Wire Claude to an MCP server. API key goes in `.env`. It works, ship it.

**Week 3**: A second agent needs the same MCP server. Copy the API key into another `.env`. Maybe a different repo.

**Week 5**: A contractor joins. They get the `.env` file in Slack. Now the key is in Slack's message history.

**Week 8**: You want to give the research agent access to the filesystem but not the database. There is no mechanism for this. Both agents share the same API key. It's all or nothing.

**Week 10**: Costs spike. You have no idea which agent made which calls. You grep through logs and find nothing useful.

**Week 12**: A teammate leaves. You rotate the API key. You now have to update it in 7 places across 4 repos. One repo gets missed. The old key sits in that repo's git history indefinitely.

---

## The four infrastructure gaps

### 1. No agent identity

Every AI agent in your system uses the same API key, or worse, uses the upstream service's master key directly. You cannot tell, from a log line, which agent made a call. You cannot revoke access to one agent without revoking all of them. You cannot rate-limit one agent without rate-limiting all of them.

The "fix" teams apply: naming conventions in environment variables. `GITHUB_TOKEN_RESEARCH_AGENT`, `GITHUB_TOKEN_WRITER_AGENT`. These are not tracked, not audited, not revocable independently.

### 2. Secrets in env files

MCP servers need credentials: API keys, OAuth tokens, database passwords. These end up in:
- `.env` files committed to repos (intentionally or by accident)
- Slack messages between engineers
- CI/CD environment variables with no rotation policy
- Hardcoded in agent prompts ("use this token to authenticate: sk-...")

A single exposed API key can result in thousands of dollars in charges overnight. In 2023, a GitHub researcher found over 100,000 live API keys in public repos in a single week-long scan. The same pattern is repeating with MCP credentials.

Building a proper secrets management solution (encryption at rest, per-service scoping, injection at runtime, rotation without downtime) takes 2–3 weeks of senior engineering time to do correctly. Most teams skip it.

### 3. No per-tool access control

MCP servers expose multiple tools: `read_file`, `write_file`, `delete_file`, `execute_command`. When an agent authenticates to an MCP server, it gets access to all of them. There is no mechanism to say "this agent can read files but not execute commands."

The blast radius of a prompt injection or a misbehaving agent is the entire surface of the MCP server. One jailbroken agent call away from `execute_command("rm -rf /")`.

Teams that try to solve this split tools across separate MCP servers, one for reads and one for writes. This is operationally painful and doesn't scale.

### 4. No audit trail

When an agent makes a tool call, what gets logged? Usually: nothing useful. You might get an HTTP access log with a timestamp and a URL, but no information about which tool was called, what arguments were passed, what the response was, or whether it was the same call that ran 50 times.

"What did the agent actually do?" is a question most teams cannot answer after the fact. When something goes wrong (a runaway agent, an unexpected data mutation, a cost spike), the debugging session starts with nothing.

---

## What building it yourself actually costs

A proper implementation requires:

| Component | Engineering time | Ongoing maintenance |
|-----------|-----------------|---------------------|
| Agent identity + API key management | 3–5 days | Key rotation, revocation flows |
| AES-encrypted secrets vault | 3–4 days | Key rotation, migration scripts |
| Per-tool RBAC with wildcard support | 2–3 days | Permission UI, audit surface |
| Full audit logging (gapless, error paths) | 1–2 days | Log retention, search |
| Semantic cache for tool calls | 1–2 weeks | Embedding model updates, cache invalidation |
| **Total** | **3–4 weeks** | **Ongoing** |

That estimate assumes a senior engineer who has done this before. Most teams doing this for the first time add another week. The maintenance burden (rotating keys, upgrading the embedding model, extending the audit schema) is permanent.

The alternative is not building it, which means shipping without identity, secrets management, access control, or observability. That works until it doesn't.

---

## This is not a new problem

API gateway infrastructure for microservices took 10 years to mature into products like Kong and AWS API Gateway. The same infrastructure problem is now playing out for AI agents and MCP, compressed into 18 months instead of 10 years because the agent ecosystem is moving faster.

Kong and AWS API Gateway exist because teams got tired of building auth, rate limiting, and observability themselves for every service. The same moment is arriving for MCP tool infrastructure.

Arbiter is that infrastructure, pre-built, in a single Docker Compose.
