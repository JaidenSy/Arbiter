# MCP Servers

An MCP server in NexVault is a registered upstream that agents route tool calls through. NexVault proxies JSON-RPC 2.0 requests to these servers, applies RBAC, injects vault secrets, and caches responses.

## Register a server

```bash
curl -s -X POST http://localhost:8000/api/v1/mcp-servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "filesystem",
    "url": "http://mcp-filesystem:3001",
    "description": "Local filesystem read/write",
    "cache_enabled": true,
    "cache_ttl_seconds": 300,
    "cache_similarity_threshold": 0.92
  }'
```

Response:

```json
{
  "id": "c4d5e6f7-8a9b-0c1d-2e3f-4a5b6c7d8e9f",
  "name": "filesystem",
  "url": "http://mcp-filesystem:3001",
  "cache_enabled": true,
  "cache_ttl_seconds": 300,
  "cache_similarity_threshold": 0.92,
  "created_at": "2026-04-01T12:00:00Z"
}
```

The `name` field is the slug agents reference via the `X-MCP-Server` request header.

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Unique slug. Used in `X-MCP-Server` header and logs. Lowercase, hyphens allowed. |
| `url` | string | yes | Base URL of the upstream MCP server. Must be reachable from the NexVault container. |
| `description` | string | no | Human-readable description. Shown in the dashboard. |
| `cache_enabled` | bool | no | Default `true`. Set to `false` for side-effectful servers (see below). |
| `cache_ttl_seconds` | int | no | Default `300`. How long cached responses are valid. |
| `cache_similarity_threshold` | float | no | Default `0.92`. Cosine similarity floor for L3 semantic cache hits. Range 0.0–1.0. |

## URL format

The `url` is the base URL of the upstream MCP server. NexVault appends the MCP path when forwarding. Examples:

```
http://mcp-filesystem:3001          # Docker Compose service
http://127.0.0.1:3001               # Localhost (if running outside Docker)
https://my-mcp-server.example.com   # Remote server
```

Do not include a trailing path. NexVault constructs the full request URL.

## The `cache_enabled` flag

This flag controls whether NexVault caches responses from this server and serves cached results on future matching requests.

**Set `cache_enabled: false` for servers that have side effects** — anything that sends messages, charges money, mutates external state, or produces time-sensitive results:

```bash
# Register a Stripe MCP server — never serve stale cached responses
curl -s -X POST http://localhost:8000/api/v1/mcp-servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "stripe",
    "url": "http://mcp-stripe:3002",
    "cache_enabled": false
  }'
```

**Set `cache_enabled: true` (or omit it) for read-heavy, idempotent servers** — file reads, database queries, search indexes, reference data:

```bash
curl -s -X POST http://localhost:8000/api/v1/mcp-servers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "postgres-readonly",
    "url": "http://mcp-pg:3003",
    "cache_enabled": true,
    "cache_ttl_seconds": 60
  }'
```

When `cache_enabled` is `false`, NexVault skips all three cache layers (Redis, Postgres exact, Postgres semantic) on both reads and writes. The `cache_ttl_seconds` and `cache_similarity_threshold` fields are ignored.

## How the three cache layers interact with `cache_enabled`

For servers where `cache_enabled: true`, every tool call goes through:

1. **L1 — Redis exact match**: SHA-256 hash of canonical JSON params. O(1). ~1ms.
2. **L2 — Postgres exact match**: same hash in the `cache_db` table. Used if Redis is cold.
3. **L3 — Postgres semantic match**: cosine similarity between the incoming request embedding and stored embeddings. Threshold: `cache_similarity_threshold`.

On a cache miss at all three layers, the request goes upstream, and the response is written to Redis + Postgres asynchronously (non-blocking).

See [vault.md](./vault.md) for how secrets are injected before the request is forwarded.

## List registered servers

```bash
curl -s http://localhost:8000/api/v1/mcp-servers
```

## Update a server

```bash
curl -s -X PATCH http://localhost:8000/api/v1/mcp-servers/c4d5e6f7-... \
  -H "Content-Type: application/json" \
  -d '{"cache_ttl_seconds": 600}'
```

## Delete a server

```bash
curl -s -X DELETE http://localhost:8000/api/v1/mcp-servers/c4d5e6f7-...
```

Deleting a server removes all associated permissions from the `tool_permissions` table. Cached responses are not immediately purged from Redis or Postgres — they expire naturally according to `cache_ttl_seconds`.

## `tools/list` filtering

When an agent calls `tools/list` on a server, NexVault filters the returned tool list to only include tools the agent has permission to call. Agents never see tool names they are not permitted to use — this prevents information leakage about the server's capabilities.

```bash
# Agent sends tools/list
curl -s -X POST http://localhost:8000/api/v1/proxy/tool-call \
  -H "Authorization: Bearer nxai_..." \
  -H "X-MCP-Server: filesystem" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

The response only contains tools the agent is permitted to call — not the full list exposed by the upstream server.
