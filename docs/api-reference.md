# API Reference

Base URL: `http://localhost:8000/api/v1`

All endpoints except the proxy tool-call route accept and return `application/json`. Interactive docs available at `/docs`.

## Authentication

Most endpoints require a Bearer API key issued when an agent is registered:

```
Authorization: Bearer nxai_<64-hex-characters>
```

Keys are only shown once at registration. If lost, delete the agent and re-register.

## Error shape

All errors follow this structure:

```json
{
  "detail": "Human-readable error message"
}
```

## Status codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Resource created |
| 204 | Success, no response body |
| 400 | Bad request / validation error |
| 401 | Missing or invalid API key |
| 402 | Plan limit reached (upgrade required) |
| 403 | Permission denied (RBAC or insufficient role) |
| 404 | Resource not found |
| 409 | Conflict (duplicate name) |
| 422 | Unprocessable entity (validation error) |
| 429 | Rate limit exceeded (login attempts) |
| 503 | Service unavailable (health probe failed) |

---

## Agents

### POST /agents

Register a new agent. Returns the raw API key exactly once.

**Auth**: Required (owner or admin role)

**Request body**:

```json
{
  "name": "my-claude-agent",
  "description": "Optional description",
  "scope": "full"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique display name for the agent |
| `description` | string | No | Optional human-readable description |
| `scope` | string | No | Permission scope — see [Agent Scopes](#agent-scopes). Defaults to `"full"` |

**Response** `201`:

```json
{
  "id": "3f7a1b2c-...",
  "name": "my-claude-agent",
  "description": "Optional description",
  "is_active": true,
  "scope": "full",
  "created_at": "2026-04-01T12:00:00Z",
  "updated_at": "2026-04-01T12:00:00Z",
  "api_key": "nxai_a1b2c3d4e5f6..."
}
```

`api_key` is not stored and will not appear in any other response.

**Errors**: `409` if an agent with this name already exists; `422` if `scope` is not one of the valid values.

```bash
curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{"name": "my-claude-agent", "description": "Research agent", "scope": "read_only"}'
```

---

### Agent Scopes

The `scope` field controls what an agent's API key is allowed to do, independently of per-tool RBAC permissions. Both checks must pass — an agent needs both the correct scope and a matching tool permission.

| Scope | Tool Calls | Vault Write | Vault Read |
|-------|-----------|-------------|------------|
| `full` | ✅ | ✅ | ✅ |
| `read_only` | ✅ | ❌ | ✅ |
| `vault_read_only` | ❌ | ❌ | ✅ |

- **`full`** — Default. Agent can make tool calls, read and write vault secrets.
- **`read_only`** — Agent can call tools but cannot create, update, or delete vault secrets. Useful for analysis agents that should never store new credentials.
- **`vault_read_only`** — Agent can only read vault secrets via the vault endpoint. All tool calls via the proxy are rejected with `403`. Useful for credential-fetching automation that should never interact with MCP servers.

Scope cannot be changed after creation. Delete and re-register the agent to change its scope.

---

### GET /agents

List all active agents, paginated.

**Auth**: Required

**Query params**:

| Param | Default | Description |
|-------|---------|-------------|
| `skip` | 0 | Offset |
| `limit` | 50 | Max records (capped at 200) |

**Response** `200`: Array of agent objects (no `api_key` field).

```json
[
  {
    "id": "3f7a1b2c-...",
    "name": "my-claude-agent",
    "description": "Research agent",
    "is_active": true,
    "scope": "full",
    "created_at": "2026-04-01T12:00:00Z",
    "updated_at": "2026-04-01T12:00:00Z"
  }
]
```

```bash
curl -s http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer nxai_..."
```

---

### GET /agents/{agent_id}

Get a single agent by UUID.

**Auth**: Required

**Response** `200`: Agent object. **Errors**: `404` if not found or inactive.

```bash
curl -s http://localhost:8000/api/v1/agents/3f7a1b2c-... \
  -H "Authorization: Bearer nxai_..."
```

---

### DELETE /agents/{agent_id}

Soft-delete an agent (sets `is_active=false`). Historical sessions and audit events are preserved.

**Auth**: Required (owner or admin)

**Response** `204`: No body.

```bash
curl -s -X DELETE http://localhost:8000/api/v1/agents/3f7a1b2c-... \
  -H "Authorization: Bearer nxai_..."
```

---

### POST /agents/{agent_id}/rotate-key

Invalidate the current API key and issue a new one. The old key is immediately rejected. The new raw key is returned exactly once.

**Auth**: Required (owner or admin)

**Response** `200`: Same shape as `POST /agents` response, including the new `api_key`.

**Errors**: `404` if the agent is not found or inactive.

```bash
curl -s -X POST http://localhost:8000/api/v1/agents/3f7a1b2c-.../rotate-key \
  -H "Authorization: Bearer nxai_..."
```

---

## MCP Servers

### POST /mcp-servers

Register a new MCP server.

**Auth**: Required

**Request body**:

```json
{
  "name": "filesystem",
  "base_url": "http://mcp-filesystem:8080",
  "description": "Local filesystem MCP server",
  "cache_enabled": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique name (1–255 chars) |
| `base_url` | string | Yes | Full HTTP(S) URL of the MCP server |
| `description` | string | No | Optional description |
| `cache_enabled` | boolean | No | Default `true`. Set `false` for servers with side effects (email, payments, etc.) |

**Response** `201`:

```json
{
  "id": "c4d5e6f7-...",
  "name": "filesystem",
  "base_url": "http://mcp-filesystem:8080",
  "description": "Local filesystem MCP server",
  "is_active": true,
  "cache_enabled": true
}
```

**Errors**: `409` if a server with this name already exists.

```bash
curl -s -X POST http://localhost:8000/api/v1/mcp-servers \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{"name": "filesystem", "base_url": "http://mcp-filesystem:8080", "cache_enabled": true}'
```

---

### GET /mcp-servers

List active MCP servers.

**Auth**: Required

**Query params**: `skip` (default 0), `limit` (default 50, max 200)

**Response** `200`: Array of server objects.

```bash
curl -s http://localhost:8000/api/v1/mcp-servers \
  -H "Authorization: Bearer nxai_..."
```

---

### GET /mcp-servers/{server_id}

Get a single MCP server.

**Auth**: Required. **Errors**: `404`.

```bash
curl -s http://localhost:8000/api/v1/mcp-servers/c4d5e6f7-... \
  -H "Authorization: Bearer nxai_..."
```

---

### PATCH /mcp-servers/{server_id}

Partially update a server. Only fields present in the body are updated.

**Auth**: Required

**Request body** (all fields optional):

```json
{
  "name": "filesystem-v2",
  "base_url": "http://mcp-filesystem-v2:8080",
  "description": "Updated description",
  "cache_enabled": false
}
```

**Response** `200`: Updated server object. **Errors**: `404`.

```bash
curl -s -X PATCH http://localhost:8000/api/v1/mcp-servers/c4d5e6f7-... \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{"cache_enabled": false}'
```

---

### DELETE /mcp-servers/{server_id}

Soft-delete a server.

**Auth**: Required. **Response** `204`. **Errors**: `404`.

```bash
curl -s -X DELETE http://localhost:8000/api/v1/mcp-servers/c4d5e6f7-... \
  -H "Authorization: Bearer nxai_..."
```

---

## Tool Permissions (RBAC)

### POST /agents/{agent_id}/permissions

Grant an agent permission to call a tool on an MCP server.

**Auth**: Required

**Request body**:

```json
{
  "mcp_server_id": "c4d5e6f7-...",
  "tool_name": "read_file",
  "rate_limit_per_minute": 60,
  "cache_ttl_seconds": 300
}
```

Use `"tool_name": "*"` to grant access to all tools on the server.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mcp_server_id` | UUID | Yes | The registered MCP server |
| `tool_name` | string | Yes | Exact tool name, or `*` for all tools |
| `rate_limit_per_minute` | integer | No | Max calls per minute for this agent+tool combination. `null` means unlimited. |
| `cache_ttl_seconds` | integer | No | Override the global cache TTL for this tool (in seconds). `null` uses the global default. |

**Response** `201`:

```json
{
  "id": "b1c2d3e4-...",
  "agent_id": "3f7a1b2c-...",
  "mcp_server_id": "c4d5e6f7-...",
  "tool_name": "read_file",
  "rate_limit_per_minute": 60,
  "cache_ttl_seconds": 300,
  "granted_at": "2026-04-01T12:00:00Z",
  "granted_by": null
}
```

**Errors**: `404` if agent or server not found; `409` if permission already exists.

```bash
curl -s -X POST http://localhost:8000/api/v1/agents/3f7a1b2c-.../permissions \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{"mcp_server_id": "c4d5e6f7-...", "tool_name": "*", "rate_limit_per_minute": 100}'
```

---

### GET /agents/{agent_id}/permissions

List all permissions for an agent.

**Auth**: Required. **Errors**: `404` if agent not found.

**Response** `200`: Array of permission objects.

```bash
curl -s http://localhost:8000/api/v1/agents/3f7a1b2c-.../permissions \
  -H "Authorization: Bearer nxai_..."
```

---

### DELETE /agents/{agent_id}/permissions/{permission_id}

Revoke a specific permission. Hard-delete — no soft-delete for permissions.

**Auth**: Required. **Response** `204`. **Errors**: `404`.

```bash
curl -s -X DELETE \
  http://localhost:8000/api/v1/agents/3f7a1b2c-.../permissions/b1c2d3e4-... \
  -H "Authorization: Bearer nxai_..."
```

---

## Vault

### POST /vault/secrets

Store or rotate a secret, scoped to the calling agent. If a secret with the same name already exists for this agent, it is overwritten.

**Auth**: Required

**Request body**:

```json
{
  "name": "GITHUB_TOKEN",
  "value": "ghp_actual_token_value_here"
}
```

**Response** `201`: Metadata only — `value` is never returned.

```json
{
  "id": "e5f6a7b8-...",
  "name": "GITHUB_TOKEN",
  "agent_id": "3f7a1b2c-...",
  "created_at": "2026-04-01T12:00:00Z"
}
```

```bash
curl -s -X POST http://localhost:8000/api/v1/vault/secrets \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{"name": "GITHUB_TOKEN", "value": "ghp_..."}'
```

---

### GET /vault/secrets

List secret names for the calling agent. Values are never returned.

**Auth**: Required

**Response** `200`: Array of `{id, name, agent_id, created_at}` objects.

```bash
curl -s http://localhost:8000/api/v1/vault/secrets \
  -H "Authorization: Bearer nxai_..."
```

---

### GET /vault/secrets/{secret_id}

Retrieve and decrypt a secret. Returns the plaintext value.

**Auth**: Required — **owner or admin role only**. Member-role users receive `403`. This prevents low-privilege org members from extracting credentials.

**Response** `200`:

```json
{
  "id": "e5f6a7b8-...",
  "name": "GITHUB_TOKEN",
  "agent_id": "3f7a1b2c-...",
  "created_at": "2026-04-01T12:00:00Z",
  "value": "ghp_actual_token_value_here"
}
```

**Errors**: `404` if not found or owned by a different agent.

---

### DELETE /vault/secrets/{secret_id}

Permanently delete a secret. Hard-delete — no recovery.

**Auth**: Required. The secret must belong to the calling agent.

**Response** `204`. **Errors**: `404`.

```bash
curl -s -X DELETE http://localhost:8000/api/v1/vault/secrets/e5f6a7b8-... \
  -H "Authorization: Bearer nxai_..."
```

---

## Sessions

Sessions are created automatically by the proxy on the first tool call. You do not create them manually.

### GET /sessions

List sessions, optionally filtered by agent.

**Auth**: Required

**Query params**:

| Param | Default | Description |
|-------|---------|-------------|
| `agent_id` | (none) | Filter to sessions for a specific agent UUID |
| `skip` | 0 | Offset |
| `limit` | 50 | Max records (capped at 200) |

**Response** `200`: Array of session objects (no events in list response).

```json
[
  {
    "id": "f7a8b9c0-...",
    "agent_id": "3f7a1b2c-...",
    "started_at": "2026-04-01T12:00:00Z",
    "ended_at": null,
    "metadata": {},
    "events": []
  }
]
```

```bash
curl -s "http://localhost:8000/api/v1/sessions?agent_id=3f7a1b2c-..." \
  -H "Authorization: Bearer nxai_..."
```

---

### GET /sessions/{session_id}

Get a session including all audit events.

**Auth**: Required. **Errors**: `404`.

**Response** `200`: Session object with nested `events` array.

```json
{
  "id": "f7a8b9c0-...",
  "agent_id": "3f7a1b2c-...",
  "started_at": "2026-04-01T12:00:00Z",
  "ended_at": null,
  "metadata": {},
  "events": [
    {
      "id": "a1b2c3d4-...",
      "session_id": "f7a8b9c0-...",
      "mcp_server_id": "c4d5e6f7-...",
      "mcp_server_name": "filesystem",
      "tool_name": "read_file",
      "request_payload": {"path": "/src/main.py"},
      "response_payload": {"content": "..."},
      "cache_hit": false,
      "duration_ms": 42,
      "error": null,
      "occurred_at": "2026-04-01T12:00:01Z"
    }
  ]
}
```

---

### GET /sessions/{session_id}/events

Paginated events for a session. Use this instead of `GET /sessions/{id}` when a session has thousands of events.

**Auth**: Required

**Query params**: `skip` (default 0), `limit` (default 100, max 500)

**Response** `200`: Array of event objects ordered by `occurred_at` ascending.

**Errors**: `404` if session not found.

---

### GET /sessions/export

Export all session events for the org as a downloadable file. Useful for compliance audits, cost analysis, and external dashboards.

**Auth**: Required

**Query params**:

| Param | Default | Description |
|-------|---------|-------------|
| `format` | `csv` | `csv` or `json` |
| `from_date` | (none) | ISO 8601 timestamp — filter sessions started after this time |
| `to_date` | (none) | ISO 8601 timestamp — filter sessions started before this time |
| `agent_id` | (none) | Filter to a specific agent UUID |

**Response** `200`: A streaming file download.

- `format=csv` → `Content-Type: text/csv`, file named `arbiter_export_<timestamp>.csv`
- `format=json` → `Content-Type: application/json`, file named `arbiter_export_<timestamp>.json`

CSV/JSON columns: `session_id`, `agent_id`, `event_id`, `tool_name`, `mcp_server`, `cache_hit`, `duration_ms`, `error`, `occurred_at`.

```bash
# Download last 30 days as CSV
curl -s "http://localhost:8000/api/v1/sessions/export?format=csv&from_date=2026-04-14T00:00:00Z" \
  -H "Authorization: Bearer nxai_..." \
  -o arbiter_audit.csv

# Download a specific agent's events as JSON
curl -s "http://localhost:8000/api/v1/sessions/export?format=json&agent_id=3f7a1b2c-..." \
  -H "Authorization: Bearer nxai_..." \
  -o agent_events.json
```

---

## Proxy (Tool Call)

### POST /proxy/tool-call

The core gateway endpoint. Every MCP tool call from an agent goes through here.

**Auth**: Required (agent API key only — JWTs not accepted on this endpoint)

**Headers**:

| Header | Required | Description |
|--------|----------|-------------|
| `Authorization` | Yes | `Bearer nxai_<key>` |
| `X-Arbiter-Session-ID` | No | Attach this call to an existing session. If omitted, a new session is started. |
| `X-MCP-Server` | Yes | Name (slug) of the registered MCP server to forward to |

**Request body**: A valid JSON-RPC 2.0 object per the MCP spec:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "read_file",
    "arguments": {
      "path": "/src/main.py",
      "api_key": "{{GITHUB_TOKEN}}"
    }
  }
}
```

`{{SECRET_NAME}}` placeholders in `params.arguments` are replaced with decrypted vault values before the request is forwarded upstream.

**Response** `200`: JSON-RPC 2.0 response from the upstream MCP server.

**Errors**:
- `401` — invalid or missing API key
- `403` — agent not permitted to call this tool on this server, or agent scope blocks tool calls
- `404` — MCP server name not found
- `429` — rate limit exceeded for this agent+tool combination

```bash
curl -s -X POST http://localhost:8000/api/v1/proxy/tool-call \
  -H "Authorization: Bearer nxai_..." \
  -H "X-MCP-Server: filesystem" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "read_file",
      "arguments": {"path": "/src/main.py"}
    }
  }'
```

---

## Health Checks

These endpoints are unauthenticated and intended for load balancers, Railway health checks, and uptime monitors.

### GET /health

Liveness probe. Returns `200` as long as the process is running.

```bash
curl -s http://localhost:8000/health
# {"status": "ok"}
```

---

### GET /health/db

Readiness probe for the database. Executes a `SELECT 1` against Postgres. Returns `503` if the connection fails — Railway will restart the service automatically.

```bash
curl -s http://localhost:8000/health/db
# {"status": "ok"}
# or: HTTP 503 {"detail": "Database unreachable: ..."}
```

---

### GET /health/cache

Readiness probe for Redis. Sends a `PING` to the Redis instance. Returns `503` if unreachable.

```bash
curl -s http://localhost:8000/health/cache
# {"status": "ok"}
# or: HTTP 503 {"detail": "Redis unreachable: ..."}
```
