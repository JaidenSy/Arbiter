# Observability: OpenTelemetry tracing

Arbiter can export a distributed trace for every MCP request it handles. The
traces follow the OpenTelemetry **GenAI + MCP semantic conventions**. Those
conventions are still in *Development* status, so names may change. The
version Arbiter follows is pinned in `backend/app/core/telemetry.py`
(`open-telemetry/semantic-conventions-genai` at commit `f3c6d0c`, which
references core semconv v1.44.0).

Tracing is **off by default and costs nothing when off**. The OTel SDK is not
imported, no exporter runs, and nothing is added to the MCP messages Arbiter
sends upstream.

## What you get

One trace per `tools/call`, with a span for each pipeline stage. This is the
per-stage latency breakdown in your own tracing backend:

```
tools/call github__create_issue          SERVER  (POST /mcp)
├── arbiter.rbac.check                    arbiter.rbac.permitted
├── arbiter.rate_limit
├── arbiter.cache.lookup                  arbiter.cache_hit
├── arbiter.quota.check                   (skipped on cache hit)
├── arbiter.vault.inject                  arbiter.vault.target=arguments
├── arbiter.vault.inject                  arbiter.vault.target=server_headers
└── tools/call create_issue               CLIENT  (upstream MCP server)
```

- **SERVER span** on `/mcp`, named `{mcp.method.name} {target}`, for example
  `tools/call github__create_issue`, `tools/list` or `initialize`. Its
  attributes are `mcp.method.name`, `jsonrpc.request.id`,
  `mcp.protocol.version`, `mcp.session.id`, `network.transport=tcp`, and for
  tool calls `gen_ai.operation.name=execute_tool` and `gen_ai.tool.name`. The
  span also carries the Arbiter ids `arbiter.session_id`, `arbiter.event_id`
  and `arbiter.cache_hit`, so you can jump from a trace to the audit log.
- **Errors** set `error.type`. A JSON-RPC error sets it to the error code (for
  example `-32601`) and also sets `rpc.response.status_code`. A tool result
  with `isError: true`, which includes RBAC denials, rate limits and quota
  errors, sets it to `tool_error`. An upstream timeout sets it to `timeout`.
- **The upstream CLIENT span** records `server.address` and `server.port`. It
  never records the URL path or query, because those can carry tokens.
- **REST proxy** calls (`POST /api/v1/proxy/tool-call`) get a SERVER span
  named `execute_tool {server}__{tool}` with the same child spans.

### Linking to the audit log

The OTel trace id is also written to Arbiter's own records:

- Every successful `tools/call` response includes it in `result._meta.arbiter.trace_id`.
- A new Arbiter session stores the trace that created it in
  `sessions.metadata.otel_trace_id`.

## Enabling it

Set these on the backend:

| Variable | Purpose |
|---|---|
| `OTEL_ENABLED=true` | Arbiter's master switch (default `false`). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP/HTTP collector base URL, e.g. `http://localhost:4318`. Required: with no endpoint, tracing stays off. `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` also works. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Auth headers for hosted backends (`key=value,key2=value2`). |
| `OTEL_SERVICE_NAME` | Defaults to `arbiter-gateway`. |
| `OTEL_SDK_DISABLED=true` / `OTEL_TRACES_EXPORTER=none` | The standard OTel kill switches. Each one turns tracing off whatever the other settings say. |
| `OTEL_CAPTURE_TOOL_CONTENT=true` | **Opt-in.** Records `gen_ai.tool.call.arguments` and `gen_ai.tool.call.result`, truncated to 8 KB. See the warning below. |

The exporter is OTLP over HTTP with protobuf encoding. It reads all the other
standard `OTEL_EXPORTER_OTLP_*` variables (timeout, compression, certificates)
directly.

The SDK reads the `OTEL_*` variables from the **process environment**. Docker
compose's `env_file: .env` exports them into the container. If you run
`uvicorn` directly, export them in your shell, because a `.env` file alone only
feeds Arbiter's own settings (`OTEL_ENABLED`, `OTEL_CAPTURE_TOOL_CONTENT`).

> **Content capture.** Tool arguments and results are never put on spans
> unless you turn on `OTEL_CAPTURE_TOOL_CONTENT`. Even then, the arguments
> recorded are the ones the client sent, with vault placeholders such as
> `{{GITHUB_TOKEN}}` left unresolved. Injected secret values and resolved
> server auth headers are never recorded. Tool *results* are recorded as the
> upstream returned them, so if an upstream server echoes a secret back, that
> secret will appear in the result attribute.

### Jaeger (local)

```bash
docker run --rm -p 16686:16686 -p 4318:4318 jaegertracing/jaeger:latest
```

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

Open http://localhost:16686 and select the service `arbiter-gateway`. With
docker compose, point the endpoint at the Jaeger service name, e.g.
`http://jaeger:4318`.

### Honeycomb

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io
OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=<your-ingest-key>
```

For EU accounts, use `https://api.eu1.honeycomb.io`.

### Grafana (Tempo / Grafana Cloud)

To try it locally, run the all-in-one image (Grafana, Tempo and a collector):

```bash
docker run --rm -p 3001:3000 -p 4318:4318 grafana/otel-lgtm
```

Then set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` and open the
Explore → Tempo view at http://localhost:3001.

For Grafana Cloud, use the OTLP endpoint and the Basic-auth header from your
stack's *OpenTelemetry* connection page:

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-<zone>.grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20<base64 of instanceId:token>
```

## Chaining Claude Code's traces into the gateway

Arbiter joins an existing trace when the request carries W3C trace context. It
looks in two places:

1. **`params._meta.traceparent` / `tracestate` / `baggage`** on the MCP
   request. This is how the MCP semantic conventions propagate context. If
   present, it becomes the parent of the SERVER span, and the HTTP-level
   `traceparent` is attached as a span **link**.
2. **The HTTP `traceparent` header**, used as the parent when `_meta` has no
   trace context.

Arbiter then injects its own context into `params._meta` on the upstream
`tools/call`. An instrumented upstream MCP server therefore continues the same
trace.

Claude Code (beta tracing) sends `traceparent` as an **HTTP header** on its
outbound HTTP MCP requests, so it is picked up by path 2. To get one trace from
the prompt down to the upstream tool, set the following where Claude Code runs:

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1        # traces are beta
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318   # same collector as Arbiter
# Only if you also route model traffic through a custom ANTHROPIC_BASE_URL:
# export CLAUDE_CODE_PROPAGATE_TRACEPARENT=1
```

Then connect Claude Code to Arbiter's HTTP MCP endpoint (see
[mcp-endpoint.md](./mcp-endpoint.md)). The resulting tree is:

```
claude_code.interaction
└── claude_code.tool
    └── claude_code.tool.execution
        └── tools/call github__create_issue      (Arbiter, SERVER)
            ├── arbiter.rbac.check …
            └── tools/call create_issue           (Arbiter → upstream, CLIENT)
```

Notes:

- Claude Code sends `traceparent` to MCP servers only when `ANTHROPIC_BASE_URL`
  is unset or points at the Anthropic API. If you use a custom base URL, set
  `CLAUDE_CODE_PROPAGATE_TRACEPARENT=1`.
- With `claude -p` and the Agent SDK, Claude Code reads an inbound
  `TRACEPARENT`/`TRACESTATE` from its environment. An orchestrator can
  therefore parent the whole run: orchestrator → Claude Code → Arbiter →
  upstream MCP server.
- Claude Code redacts tool inputs on its own spans unless
  `OTEL_LOG_TOOL_DETAILS=1`. Arbiter's equivalent setting is
  `OTEL_CAPTURE_TOOL_CONTENT`.
- Stdio MCP servers that Claude Code launches directly are outside Arbiter.
  This chaining applies to the HTTP `/mcp` endpoint.
