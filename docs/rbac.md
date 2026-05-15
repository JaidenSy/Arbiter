# RBAC

NexVault enforces access control at two independent layers. Both must pass for a tool call to succeed.

## Layer 1 — Agent Scope

Every agent has a `scope` field set at registration time. It restricts what the agent's key can do at a high level, before per-tool checks run.

| Scope | Tool Calls | Vault Write | Vault Read |
|-------|-----------|-------------|------------|
| `full` | ✅ | ✅ | ✅ |
| `read_only` | ✅ | ❌ | ✅ |
| `vault_read_only` | ❌ | ❌ | ✅ |

A `vault_read_only` agent hitting the proxy will receive `403 Forbidden` before the tool-level check even runs. A `read_only` agent can call any permitted tool but cannot write secrets via `POST /vault/secrets`.

Scope is set at creation and cannot be changed — delete and re-register to change scope.

```bash
# Register a read-only agent
curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{"name": "analysis-agent", "scope": "read_only"}'
```

## Layer 2 — Tool Permissions

A permission record says: "Agent X is allowed to call tool Y on server Z."

- `agent_id` — UUID of the agent
- `mcp_server_id` — UUID of the registered MCP server
- `tool_name` — exact tool name, or `*` to grant all tools on that server

The check is a single indexed SQL `EXISTS` query on the hot path. If no matching row exists, the request is rejected with `403 Forbidden`.

## Granting a permission

### Grant a specific tool

```bash
curl -s -X POST http://localhost:8000/api/v1/agents/3f7a1b2c-.../permissions \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{
    "mcp_server_id": "c4d5e6f7-...",
    "tool_name": "read_file"
  }'
```

### Grant with rate limiting

Limit how many times an agent can call a tool per minute. When exceeded, the gateway returns `429 Too Many Requests` without forwarding to the upstream server.

```bash
curl -s -X POST http://localhost:8000/api/v1/agents/3f7a1b2c-.../permissions \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{
    "mcp_server_id": "c4d5e6f7-...",
    "tool_name": "web_search",
    "rate_limit_per_minute": 20
  }'
```

Omit `rate_limit_per_minute` (or set to `null`) for unlimited calls.

### Grant with a custom cache TTL

Override the global cache TTL for a specific tool. Useful when a tool's results are short-lived (e.g. live stock prices) or very stable (e.g. static config reads).

```bash
curl -s -X POST http://localhost:8000/api/v1/agents/3f7a1b2c-.../permissions \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{
    "mcp_server_id": "c4d5e6f7-...",
    "tool_name": "get_stock_price",
    "cache_ttl_seconds": 30
  }'
```

If `cache_ttl_seconds` is set on both a specific-tool permission and a wildcard `*` permission, the specific-tool value takes precedence. If neither is set, the global `CACHE_TTL_SECONDS` environment variable is used.

### Grant all tools on a server (wildcard)

```bash
curl -s -X POST http://localhost:8000/api/v1/agents/3f7a1b2c-.../permissions \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{
    "mcp_server_id": "c4d5e6f7-...",
    "tool_name": "*"
  }'
```

The `*` wildcard matches any tool name on that server. It does not require listing tools in advance — new tools added to the upstream server are automatically accessible to agents that have the `*` grant.

### Grant specific tools via Python

```python
import httpx

NEXUS_URL = "http://localhost:8000/api/v1"
ADMIN_KEY = "nxai_..."

def grant_tool(agent_id: str, server_id: str, tool: str):
    resp = httpx.post(
        f"{NEXUS_URL}/agents/{agent_id}/permissions",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"mcp_server_id": server_id, "tool_name": tool},
    )
    resp.raise_for_status()
    return resp.json()

# Grant only read access, not write
grant_tool(agent_id, filesystem_server_id, "read_file")
grant_tool(agent_id, filesystem_server_id, "list_directory")
# NOT: grant_tool(agent_id, filesystem_server_id, "write_file")
```

## Revoking a permission

```bash
curl -s -X DELETE \
  "http://localhost:8000/api/v1/agents/3f7a1b2c-.../permissions?mcp_server_id=c4d5e6f7-...&tool_name=read_file" \
  -H "Authorization: Bearer nxai_..."
```

Revoking `*` removes the wildcard grant but does not remove individual tool grants. Revoking a specific tool name only removes that specific record.

## Listing an agent's permissions

```bash
curl -s http://localhost:8000/api/v1/agents/3f7a1b2c-.../permissions \
  -H "Authorization: Bearer nxai_..."
```

Response:

```json
[
  {
    "mcp_server_id": "c4d5e6f7-...",
    "mcp_server_name": "filesystem",
    "tool_name": "read_file",
    "granted_at": "2026-04-01T12:00:00Z"
  },
  {
    "mcp_server_id": "c4d5e6f7-...",
    "mcp_server_name": "filesystem",
    "tool_name": "list_directory",
    "granted_at": "2026-04-01T12:01:00Z"
  }
]
```

## 403 behavior

When an agent calls a tool it is not permitted to use, the gateway returns:

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "detail": "Agent does not have permission to call tool 'write_file' on server 'filesystem'"
}
```

The call is also logged as a `SessionEvent` with `outcome: "permission_denied"`. Permission-denied events appear in the audit log alongside successful calls — gaps in the audit log are not possible.

The agent is also not told the tool exists. When calling `tools/list`, only permitted tools are returned. An agent cannot enumerate what it cannot call.

## Example: locking down a read-only research agent

```python
import httpx

NEXUS_URL = "http://localhost:8000/api/v1"
ADMIN_KEY = "nxai_..."

# Register a research agent
agent = httpx.post(
    f"{NEXUS_URL}/agents",
    headers={"Authorization": f"Bearer {ADMIN_KEY}"},
    json={"name": "research-agent", "description": "Read-only research"},
).json()

agent_id = agent["id"]
# Save agent["api_key"] — it is shown once

# Get the filesystem server ID
servers = httpx.get(
    f"{NEXUS_URL}/mcp-servers",
    headers={"Authorization": f"Bearer {ADMIN_KEY}"},
).json()
filesystem_id = next(s["id"] for s in servers if s["name"] == "filesystem")

# Grant only read-only tools — no write_file, no delete_file
for tool in ["read_file", "list_directory", "search_files"]:
    httpx.post(
        f"{NEXUS_URL}/agents/{agent_id}/permissions",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"mcp_server_id": filesystem_id, "tool_name": tool},
    )
```

## Example: per-customer agent isolation

For multi-tenant applications where each customer has their own agent:

```python
def provision_customer_agent(customer_id: str, allowed_tools: list[str]) -> dict:
    # Create an agent per customer
    agent = httpx.post(
        f"{NEXUS_URL}/agents",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={
            "name": f"customer-{customer_id}",
            "description": f"Agent for customer {customer_id}",
        },
    ).json()

    # Grant only the tools this customer tier has access to
    for tool in allowed_tools:
        httpx.post(
            f"{NEXUS_URL}/agents/{agent['id']}/permissions",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            json={"mcp_server_id": your_server_id, "tool_name": tool},
        )

    return {"agent_id": agent["id"], "api_key": agent["api_key"]}

# Free tier: read only
free_agent = provision_customer_agent("cust_001", ["read_document", "search"])

# Pro tier: full access
pro_agent = provision_customer_agent("cust_002", ["*"])
```

Each customer's agent has its own API key, its own vault namespace, and its own permission set. Customers cannot access each other's tools or secrets.

## How the wildcard `*` is evaluated

The SQL check is:

```sql
SELECT EXISTS (
  SELECT 1 FROM tool_permissions
  WHERE agent_id = $1
    AND mcp_server_id = $2
    AND (tool_name = $3 OR tool_name = '*')
)
```

The `*` row matches any `tool_name` value passed as `$3`. There is no pattern matching beyond this — `read_*` is not a valid wildcard pattern. Use `*` for full server access, or enumerate specific tools for granular control.
