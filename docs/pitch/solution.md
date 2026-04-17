# The Solution

NexVault sits between your AI agents and your MCP servers. Every tool call passes through it. In exchange for that position, it gives you agent identity, encrypted secrets, per-tool access control, a semantic cache, and a gapless audit log.

---

## How each problem is solved

### Agent identity: `nxai_` prefixed API keys

Each agent gets a unique API key in the format `nxai_<64-hex-chars>`. The raw key is shown once and never stored. What NexVault stores is `SHA-256(raw_key)` — a one-way hash. When a request arrives, the bearer token is hashed and compared with `hmac.compare_digest` (timing-safe) against stored hashes.

The `nxai_` prefix is intentional. It makes keys grep-able. If a key leaks into a log file, a GitHub Actions log, or a Slack message, you can search for `nxai_` and find it. Generic UUIDs are invisible in noisy output.

Each agent has its own key. Compromising one agent's key does not affect others. Revoking access is one API call — delete the agent, the hash is gone, the key is dead.

### Secrets: AES-256-GCM vault with `{{SECRET_NAME}}` injection

Credentials your agents need — GitHub tokens, Slack keys, database passwords — are stored in the vault encrypted with AES-256-GCM. Each write generates a fresh 96-bit random nonce. The nonce is prepended to the ciphertext and both are stored in Postgres. The plaintext is discarded immediately after encryption.

At request time, the proxy scans `params.arguments` for `{{SECRET_NAME}}` placeholders. For each match, it decrypts the secret in-memory, substitutes the value, and forwards to the upstream MCP server. The plaintext never touches disk, never appears in logs, never travels back to the calling agent.

Secrets are scoped per agent. Agent A's `GITHUB_TOKEN` is a different row from Agent B's `GITHUB_TOKEN`. Neither can read the other's.

```json
{
  "params": {
    "name": "github_create_pr",
    "arguments": {
      "token": "{{GITHUB_TOKEN}}",
      "repo": "my-org/my-repo",
      "title": "Fix auth bug"
    }
  }
}
```

The upstream MCP server receives the real token. Your agent code contains only `{{GITHUB_TOKEN}}`.

### RBAC: flat permissions table, wildcard support

Permissions live in a flat `tool_permissions(agent_id, mcp_server_id, tool_name)` table. Every tool call triggers a single indexed SQL `EXISTS` check before anything else runs. No middleware chain, no policy engine, no external service call.

To grant all tools on a server: `tool_name = "*"`. To restrict to specific tools: list them individually.

```bash
# Research agent: read-only on filesystem
grant(agent="research", server="filesystem", tool="read_file")
grant(agent="research", server="filesystem", tool="list_directory")

# Ops agent: full access
grant(agent="ops", server="filesystem", tool="*")
```

Agents that call tools they are not permitted to use receive `403 Forbidden`. The tool call is logged. The tool name is also hidden from `tools/list` responses — agents cannot enumerate tools they cannot call.

### Observability: gapless audit log

Every tool call produces a `SessionEvent` row:

| Field | Value |
|-------|-------|
| `agent_id` | which agent called |
| `mcp_server_id` | which server was targeted |
| `tool_name` | which tool was called |
| `request_payload` | full JSON-RPC params |
| `response_payload` | full upstream response |
| `cache_hit` | `true`/`false`, and which layer (L1/L2/L3) |
| `duration_ms` | end-to-end latency |
| `outcome` | `success`, `permission_denied`, `upstream_error`, `timeout` |

Every outcome is logged. Permission denials, timeouts, and upstream errors are not filtered out. An audit log with gaps is not an audit log.

Sessions group related calls. If your agent sends `X-NexVault-Session-ID` across calls, they appear as a single trace in the dashboard — you can see the full tool call sequence for one agent run.

### Semantic cache: 3-layer, MCP tool call-specific

The cache operates on tool call results, not LLM completions. This is different from what Portkey and LiteLLM cache.

```
Incoming tool call
       |
       v
L1: Redis exact match
    SHA-256(canonical JSON params) → O(1), ~1ms
    HIT → return immediately
       |
       v (miss)
L2: Postgres exact match
    same hash, used when Redis is cold
    HIT → return + repopulate Redis
       |
       v (miss)
L3: Postgres cosine similarity
    embed incoming params, compare against stored embeddings
    threshold: 0.92 (configurable per server)
    HIT → return cached result for semantically equivalent call
       |
       v (miss at all layers)
Upstream MCP server
    real network call
    response stored async → Redis + Postgres
```

"list files in /src" and "show me what's in /src" embed to vectors with cosine similarity > 0.92. They return the same cached result. The upstream server is called once.

Cache is disabled per-server for side-effectful operations (payment processing, email sending, state mutations). The `cache_enabled` flag on each registered server controls this.

---

## Data flow

```
Agent (Claude / script)
        |
        | POST /api/v1/proxy/tool-call
        | Authorization: Bearer nxai_<key>
        v
+-------+----------------------------------------------------------+
|                     FastAPI Gateway (:8000)                       |
|                                                                   |
|  1. get_current_agent()                                           |
|     SHA-256(bearer_token) → agents.api_key_hash lookup           |
|     Fail → 401                                                    |
|                                                                   |
|  2. RBACService.check_permission(agent, server, tool)             |
|     SELECT EXISTS tool_permissions                                |
|     Fail → 403                                                    |
|                                                                   |
|  3. CacheService.get_cached(tool_name, params)                    |
|     └─ L1: Redis GETEX cache:<tool>:<hash>    ─── HIT → return  |
|     └─ L2: Postgres exact hash match          ─── HIT → return  |
|     └─ L3: Postgres cosine similarity search  ─── HIT → return  |
|                                                                   |
|  4. ProxyService.intercept_request()                              |
|     Replace {{SECRET_NAME}} → VaultService.get_secret()          |
|     Decrypt AES-256-GCM ciphertext → plaintext                   |
|                                                                   |
|  5. httpx.AsyncClient POST → MCP Server                           |
|     ┌───────────────────────────────┐                            |
|     │  MCP Server (filesystem, etc) │                            |
|     │  returns JSON response        │                            |
|     └───────────────────────────────┘                            |
|                                                                   |
|  6. CacheService.store_cached()                                   |
|     Write to Redis (L1) + Postgres (L2) with TTL                 |
|                                                                   |
|  7. Persist SessionEvent (audit log)                              |
|     tool_name, request, response, cache_hit, duration_ms         |
|                                                                   |
|  8. Return ToolCallResponse                                       |
+-------------------------------------------------------------------+

Supporting stores:
  ┌──────────┐    ┌──────────┐    ┌─────────────┐
  │ Postgres │    │  Redis   │    │  FastEmbed  │
  │  :5432   │    │  :6379   │    │ (in-process)│
  │          │    │          │    │             │
  │ agents   │    │ L1 cache │    │ all-MiniLM  │
  │ sessions │    │ sessions │    │ L6-v2 ONNX  │
  │ events   │    │          │    │ 10-15ms CPU │
  │ cache_db │    │          │    └─────────────┘
  │ vault    │    │          │
  └──────────┘    └──────────┘
```

---

## What you get out of the box

- FastAPI gateway (asyncpg, full async)
- Postgres 16 (agents, sessions, audit log, cache, vault)
- Redis (L1 cache, session mapping)
- FastEmbed `all-MiniLM-L6-v2` ONNX runtime (in-process, ~10ms, no PyTorch)
- React dashboard (Vite + TailwindCSS + TanStack Query)

```bash
git clone https://github.com/your-org/nexvault && cd nexvault
cp .env.example .env
docker compose up --build
```

That's it. No cloud account. No Kubernetes. No external services. The API is at `http://localhost:8000`. The dashboard is at `http://localhost:3000`.

For production deployment on Railway or Fly.io, see [self-hosting.md](../self-hosting.md).
