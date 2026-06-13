# Native MCP Endpoint

Arbiter is itself an MCP server. Any MCP client — Claude Code, Claude Desktop, Cursor, VS Code, Windsurf, or your own agent built on an MCP SDK — connects to the gateway with a single URL. No custom integration code, no SDK required.

Every tool call made through this endpoint runs the full gateway pipeline: RBAC, vault secret injection, semantic cache, quotas, per-session budgets, rate limits, and the audit log. It is the same pipeline as the [REST proxy](./api-reference.md) — just spoken in MCP.

## Connect a client

Add Arbiter to your MCP client config (`.mcp.json`, `claude_desktop_config.json`, etc.):

```json
{
  "mcpServers": {
    "arbiter": {
      "type": "http",
      "url": "https://api.arbiterai.dev/mcp",
      "headers": {
        "Authorization": "Bearer nxai_your_agent_key"
      }
    }
  }
}
```

If your client cannot send custom headers, embed the agent key in the URL instead:

```json
{
  "mcpServers": {
    "arbiter": {
      "type": "http",
      "url": "https://api.arbiterai.dev/mcp/nxai_your_agent_key"
    }
  }
}
```

> ⚠️ The key-in-URL form makes the full URL a secret. Prefer the `Authorization` header whenever your client supports it. URLs can end up in logs and shell history.

Self-hosted deployments expose the same endpoint at `http://localhost:8000/mcp`.

## How tools appear

The gateway aggregates **all active MCP servers in your org** into one virtual server. Tool names are namespaced with a double underscore:

```
<server_name>__<tool_name>

github__create_issue
filesystem__read_file
slack__post_message
```

`tools/list` advertises every tool from your registered servers, including ones the calling agent has no permission for. RBAC is enforced exclusively at call time: a denied `tools/call` returns a spec-compliant `isError` result with an explicit denial message, and the denial is recorded as a session event in the audit log — visible enforcement in traces rather than silently hidden tools. The aggregated list is cached per-agent for 60 seconds.

Server names cannot contain `__` (rejected at registration) so the split is unambiguous; tool names may contain `__`.

## Transport details

| Aspect | Behaviour |
|---|---|
| Transport | MCP Streamable HTTP — `POST /mcp` with JSON-RPC 2.0 bodies |
| Protocol versions | `2024-11-05`, `2025-03-26`, `2025-06-18` |
| Auth | `Authorization: Bearer nxai_...` (or key-in-URL) |
| Sessions | `initialize` returns an `Mcp-Session-Id` header that maps 1:1 to an Arbiter audit session — send it back on subsequent requests and every call from your client lands in one session trace |
| Server-initiated streams | Not offered; `GET /mcp` returns 405 (clients fall back automatically) |
| JSON-RPC batching | Rejected (removed from the MCP spec in 2025-06-18) |

## Errors

Failures during `tools/call` are returned as spec-compliant MCP tool errors — a `result` with `isError: true` and an explicit message — not as JSON-RPC protocol errors. This covers all gateway-side denials and upstream failures:

| Condition | Returned as |
|---|---|
| RBAC denied / scope violation | `isError: true` tool result |
| MCP server not found / inactive | `isError: true` tool result |
| Per-session budget exhausted | `isError: true` tool result |
| Rate limit or monthly quota exceeded | `isError: true` tool result |
| Upstream MCP server error/unreachable | `isError: true` tool result |

JSON-RPC protocol errors (`-32600`, `-32602`, …) are reserved for envelope problems: malformed JSON, invalid params, a tool name that isn't `server__tool`-namespaced, or an unknown method.

Example denial:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Agent 'research-agent' does not have permission to call tool 'delete_file' on server 'filesystem'"
      }
    ],
    "isError": true
  }
}
```

## Observability metadata

Successful `tools/call` results carry gateway metadata under the spec's `_meta` extension point:

```json
{
  "content": [{ "type": "text", "text": "..." }],
  "_meta": {
    "arbiter": {
      "session_id": "9be2...",
      "event_id": "77f0...",
      "cache_hit": true,
      "duration_ms": 3
    }
  }
}
```

## When to use the REST proxy instead

The [REST proxy](./api-reference.md) (`POST /api/v1/proxy/tool-call`) remains the right choice when you need explicit control: passing `parent_session_id` for multi-hop chain tracing from your own orchestration code, or calling the gateway from environments without an MCP client library.
