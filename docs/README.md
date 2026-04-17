# NexVault

NexVault is a developer-first MCP (Model Context Protocol) gateway that gives every AI agent a verified identity, a per-agent encrypted secrets vault, tool-level access control, a 3-layer semantic cache, and a gapless audit log — deployed in a single `docker compose up`.

## Problems it solves

- **No agent identity** — your Claude scripts all share one API key with no per-agent tracking
- **Secrets in env files** — API keys for downstream tools live in plaintext `.env` files or are baked into prompts
- **No access control** — any agent can call any tool; there is no allowlist or per-agent restriction
- **Repeated upstream calls** — semantically identical tool calls (e.g. "list files in /src" vs "show me /src files") hit the upstream server every time
- **Invisible audit trail** — when something breaks or costs spike, you have no record of what tool was called, by whom, with what inputs, and whether it was a cache hit

## Quick start

```bash
git clone https://github.com/your-org/nexvault && cd nexvault
cp .env.example .env  # fill in VAULT_ENCRYPTION_KEY and passwords
docker compose up -d
```

The API is available at `http://localhost:8000` and the dashboard at `http://localhost:3000`.

## Documentation

| Doc | Description |
|-----|-------------|
| [self-hosting.md](./self-hosting.md) | Full setup guide, all environment variables, upgrade instructions |
| [api-reference.md](./api-reference.md) | Every endpoint with request/response schemas and curl examples |
| [agent-integration.md](./agent-integration.md) | How to connect an AI agent to the gateway |
| [mcp-servers.md](./mcp-servers.md) | How to register MCP servers |
| [vault.md](./vault.md) | How the secrets vault works and how to use it |
| [rbac.md](./rbac.md) | Access control: granting and revoking tool permissions |

## Pitch docs

| Doc | Description |
|-----|-------------|
| [pitch/problem.md](./pitch/problem.md) | The infrastructure problem every AI team builds twice |
| [pitch/solution.md](./pitch/solution.md) | How NexVault solves it, with architecture details |
| [pitch/pricing.md](./pitch/pricing.md) | Tier breakdown and ROI rationale |
| [pitch/comparison.md](./pitch/comparison.md) | NexVault vs LiteLLM, Portkey, Kong, DIY |
| [pitch/use-cases.md](./pitch/use-cases.md) | Four buyer personas and their specific scenarios |
