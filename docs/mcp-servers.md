# MCP Servers

An MCP server in Arbiter is a registered upstream that agents route tool calls through. Arbiter proxies JSON-RPC 2.0 requests to these servers, applying RBAC, vault secret injection, rate limiting, and caching along the way.

---

## Transport requirement

Arbiter communicates with MCP servers using the **MCP Streamable HTTP transport** (the current MCP standard). Every tool call is a `POST` with:

```
Content-Type: application/json
Accept: application/json, text/event-stream
```

The server may respond with either plain JSON or an SSE-formatted body (`data: {...}\n\n`) — Arbiter handles both. The Arbiter test endpoint performs a full MCP handshake (initialize → tools/list) to validate connectivity.

> **SSE-only servers are not supported.** If your server only supports the legacy SSE transport (GET `/sse` + POST `/messages`), wrap it with supergateway (see below).

---

## URL format

`base_url` must point to the server's MCP endpoint directly — Arbiter POSTs JSON-RPC to it as-is. For Streamable HTTP servers this is typically the `/mcp` path:

```
https://my-mcp-server.example.com/mcp    # remote server
http://mcp-filesystem:3001/mcp           # Docker Compose service
http://127.0.0.1:3001/mcp               # localhost
```

**Do not** set `base_url` to just the host root unless the server explicitly serves MCP at `/`.

---

## Server types and setup

### Native Streamable HTTP servers

These servers speak Streamable HTTP out of the box (e.g. `@playwright/mcp`, most newer MCP packages). Register them directly with their `/mcp` endpoint.

```bash
# Start playwright MCP on port 3200
npx @playwright/mcp --port 3200 --headless
# base_url → http://localhost:3200/mcp
```

**Allowed-hosts**: Some servers (like `@playwright/mcp`) validate the `Host` header and only accept requests from specified origins. If you are exposing the server through a tunnel or reverse proxy, pass the tunnel hostname:

```bash
npx @playwright/mcp --port 3200 --headless --allowed-hosts your-tunnel-domain.example.com
```

Without this, requests arriving with a non-localhost `Host` header will be rejected with 403.

### stdio-only servers

Many MCP packages (e.g. `@modelcontextprotocol/server-github`, `mcpvault`) communicate via stdin/stdout and have no built-in HTTP server. Use [supergateway](https://github.com/supermachine-ai/supergateway) to bridge them to Streamable HTTP:

```bash
# Install
brew install supergateway   # macOS
npm install -g supergateway # or via npm

# Wrap a stdio server
supergateway \
  --stdio "npx -y @modelcontextprotocol/server-github" \
  --port 3300 \
  --outputTransport streamableHttp

# base_url → http://localhost:3300/mcp
```

Pass environment variables to the stdio command as normal shell env vars:

```bash
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_... supergateway \
  --stdio "npx -y @modelcontextprotocol/server-github" \
  --port 3300 \
  --outputTransport streamableHttp
```

> **`--outputTransport streamableHttp` is required.** Without it, supergateway defaults to SSE transport (served at `/sse`) which Arbiter cannot use.

---

## Exposing local servers to a hosted Arbiter

If your Arbiter backend is hosted (e.g. Railway, Fly) but your MCP servers run locally, you need a tunnel to make them reachable. [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) is free and supports multiple ingress rules in a single tunnel.

**Example config (`~/.cloudflared/config.yml`):**

```yaml
tunnel: <your-tunnel-id>
credentials-file: /path/to/<tunnel-id>.json

ingress:
  - hostname: obsidian.yourdomain.com
    service: http://localhost:3100
  - hostname: playwright.yourdomain.com
    service: http://localhost:3200
  - hostname: github.yourdomain.com
    service: http://localhost:3300
  - service: http_status:404
```

Run: `cloudflared tunnel run <tunnel-name>`

DNS records for each hostname must exist in Cloudflare and be set to **Proxied** (orange cloud).

With this setup your `base_url` values become:

```
https://obsidian.yourdomain.com/mcp
https://playwright.yourdomain.com/mcp
https://github.yourdomain.com/mcp
```

---

## Register a server

```bash
curl -s -X POST https://your-arbiter.example.com/api/v1/mcp-servers \
  -H "Authorization: Bearer <user-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "github",
    "base_url": "https://github.yourdomain.com/mcp",
    "description": "GitHub API via MCP",
    "cache_enabled": false
  }'
```

Response:

```json
{
  "id": "c4d5e6f7-8a9b-0c1d-2e3f-4a5b6c7d8e9f",
  "name": "github",
  "base_url": "https://github.yourdomain.com/mcp",
  "description": "GitHub API via MCP",
  "cache_enabled": false,
  "is_active": true,
  "created_at": "2026-04-01T12:00:00Z"
}
```

The `name` field is the slug agents use when making proxy calls (`"server_name": "github"`).

## Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | Unique slug. Used in proxy calls and logs. |
| `base_url` | string | yes | — | Full MCP endpoint URL (e.g. `https://host/mcp`). |
| `description` | string | no | null | Human-readable label shown in the dashboard. |
| `cache_enabled` | bool | no | `true` | Set `false` for side-effectful servers (see below). |

---

## Testing connectivity

Use the **Test** button in the dashboard or `POST /mcp-servers/{id}/test` to validate a server before granting agents access.

The test performs a full MCP handshake:
1. `initialize` — establishes protocol version and capabilities
2. `tools/list` — retrieves the list of available tools

On success it returns tool count and round-trip latency. On failure it returns the HTTP status or error message.

**Common failures:**

| Error | Cause | Fix |
|-------|-------|-----|
| `HTTP 406` | Server received wrong `Accept` header | Upgrade Arbiter — older versions sent `Accept: application/json` only |
| `HTTP 403` | Server rejected `Host` header | Add `--allowed-hosts <tunnel-hostname>` when starting the server |
| `HTTP 404` | Wrong `base_url` path | Ensure `base_url` ends in `/mcp`, not just the host root |
| `HTTP 502` | Arbiter can't reach the server | Check the server is running and the tunnel/URL is correct |
| `Expecting value` | Server returned SSE body that failed JSON parse | Upgrade Arbiter — older versions didn't handle SSE-formatted responses |
| `Connection refused` | Nothing listening on that port | Start the MCP server (or supergateway wrapper) first |

---

## The `cache_enabled` flag

**Set `false` for side-effectful servers** — anything that sends messages, charges money, mutates external state, or produces time-sensitive results (GitHub writes, Stripe, email, Slack).

**Set `true` (or omit) for read-heavy, idempotent servers** — file reads, database queries, search indexes, knowledge bases.

When `cache_enabled` is `false`, Arbiter skips all cache layers on both reads and writes.

---

## Disable and re-enable

Servers can be disabled without deleting them. A disabled server is invisible to agents and does not count against your active server quota, but its configuration is preserved so it can be re-enabled later.

From the dashboard: open the overflow menu (⋯) on any server row and select **Disable** or **Enable**.

Via API:

```bash
# Disable
curl -s -X PATCH https://your-arbiter.example.com/api/v1/mcp-servers/<id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# Re-enable
curl -s -X PATCH https://your-arbiter.example.com/api/v1/mcp-servers/<id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"is_active": true}'
```

On plans with an active server limit, re-enabling a server when at the limit prompts you to select an active server to swap out.

---

## Delete a server

Deletion is permanent and removes all associated tool permissions. Session history and audit events referencing the server are preserved.

```bash
curl -s -X DELETE https://your-arbiter.example.com/api/v1/mcp-servers/<id> \
  -H "Authorization: Bearer <token>"
```

---

## `tools/list` filtering

When an agent calls `tools/list`, Arbiter filters the response to only include tools that agent is permitted to call — preventing information leakage about capabilities the agent cannot access.

See [rbac.md](./rbac.md) for how to grant tool permissions to agents.
