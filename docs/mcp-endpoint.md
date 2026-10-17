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
| Protocol versions | **Modern:** `2026-07-28` (stateless). **Legacy:** `2025-11-25`, `2025-06-18`, `2025-03-26`, `2024-11-05` (initialize-based) |
| Auth | `Authorization: Bearer nxai_...` (or key-in-URL) |
| Origin | Validated on every request. A present-but-not-allowlisted `Origin` gets `403`. Allowlist = `MCP_ALLOWED_ORIGINS` (comma-separated or JSON array; `*` = any), falling back to `CORS_ORIGINS`. Requests without `Origin` (CLI/desktop clients) are unaffected |
| Sessions (legacy) | `initialize` returns an `Mcp-Session-Id` header that maps 1:1 to an Arbiter audit session — send it back on subsequent requests and every call from your client lands in one session trace |
| Sessions (modern) | No protocol sessions. Pass an Arbiter session handle to group calls — see [Audit sessions in the modern era](#audit-sessions-in-the-modern-era) |
| Server-initiated streams | Not offered; `GET /mcp` and `DELETE /mcp` return 405 |
| JSON-RPC batching | Rejected (removed from the MCP spec in 2025-06-18) |

### How the era is chosen

Arbiter is a *dual-era* server (MCP 2026-07-28, "Versioning → Backward Compatibility"). Per request:

- If `params._meta["io.modelcontextprotocol/protocolVersion"]` is present (or `MCP-Protocol-Version` names a modern version, or the method is `server/discover`), the request is served **statelessly** under 2026-07-28.
- Otherwise it is a **legacy** request: `initialize` negotiates the client's version (newest offered: `2025-11-25`), and `MCP-Protocol-Version` is validated when present (absent is treated as `2025-03-26`).

### Modern (2026-07-28) requests

Supported methods: `server/discover`, `tools/list`, `tools/call`. (`ping` and `initialize` are legacy-only and return HTTP 404 / `-32601` in the modern era.)

Every POST must carry headers that match the body:

| Header | Must equal |
|---|---|
| `MCP-Protocol-Version` | `params._meta["io.modelcontextprotocol/protocolVersion"]` |
| `Mcp-Method` | `method` |
| `Mcp-Name` | `params.name` (for `tools/call`); non-ASCII values use `=?base64?…?=` |

| Condition | HTTP | JSON-RPC error |
|---|---|---|
| Header missing, malformed, or different from the body | 400 | `-32020` HeaderMismatch |
| `_meta` protocol version not supported | 400 | `-32022` UnsupportedProtocolVersion, with `data.supported` / `data.requested` |
| `_meta` missing `protocolVersion` or `clientCapabilities` | 400 | `-32602` Invalid params |
| Unknown method | 404 | `-32601` Method not found |

Every result carries `resultType: "complete"` and `_meta["io.modelcontextprotocol/serverInfo"]`. `server/discover` returns `ttlMs: 3600000, cacheScope: "public"`; `tools/list` returns `ttlMs: 60000, cacheScope: "private"`. `tools/list` is sorted by namespaced tool name in both eras, so the order is deterministic.

### Audit sessions in the modern era

2026-07-28 removes `Mcp-Session-Id`. To keep grouping calls into one Arbiter session trace, send an explicit handle on each `tools/call`, either as a `_meta` key or a header:

```json
"_meta": {
  "io.modelcontextprotocol/protocolVersion": "2026-07-28",
  "io.modelcontextprotocol/clientCapabilities": {},
  "dev.arbiterai/sessionId": "9be2..."
}
```

or `X-Arbiter-Session-Id: 9be2...`. Every `tools/call` result returns the session it was recorded under in `_meta["dev.arbiterai/sessionId"]`. Omit the handle on the first call and reuse the returned value. A handle belonging to a different agent is ignored and a new session is created, so a handle is never treated as authentication.

### Upstream servers

When Arbiter calls your registered MCP servers, it detects each server's era the same way a dual-era client should. It probes with `server/discover` first. If that returns a recognised modern response or error, the server is treated as modern and receives stateless requests with `_meta` and `MCP-Protocol-Version` / `Mcp-Method` / `Mcp-Name`. Otherwise Arbiter falls back to `initialize` (offering `2025-11-25`), sends `notifications/initialized`, and then sends `Mcp-Session-Id` plus the negotiated `MCP-Protocol-Version` on every request. A `404` on a legacy session triggers one re-initialize and retry. The detected era is cached per server for an hour.

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
