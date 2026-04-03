# Agent Integration

## What is an "agent" in NexusAI?

An agent is any programmatic client that calls MCP tools through the NexusAI gateway — a Claude script, a LangChain workflow, a cron job, a FastAPI service, anything that makes HTTP requests. NexusAI assigns each agent:

- A unique UUID
- An API key (`nxai_<64-hex-chars>`) used to authenticate every request
- An isolated vault namespace for secrets
- A permission set controlling which tools it can call

Agents do not need to know about each other. They cannot see each other's secrets, sessions, or permissions.

## Step 1: Register an agent

```bash
curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "research-agent", "description": "Reads files and runs searches"}'
```

Response:

```json
{
  "id": "3f7a1b2c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "name": "research-agent",
  "api_key": "nxai_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
  "is_active": true,
  "created_at": "2026-04-01T12:00:00Z"
}
```

**Save the `api_key` immediately.** It is shown exactly once and is not stored. If lost, delete the agent and register again.

```python
import httpx

response = httpx.post(
    "http://localhost:8000/api/v1/agents",
    json={"name": "research-agent", "description": "Reads files and runs searches"},
)
data = response.json()
agent_id = data["id"]
api_key = data["api_key"]  # save this
```

## Step 2: Grant tool permissions

Before an agent can call any tool, you must grant it permission. See [rbac.md](./rbac.md) for full details. Quick example:

```bash
# Grant access to all tools on the "filesystem" MCP server
curl -s -X POST http://localhost:8000/api/v1/agents/3f7a1b2c-.../permissions \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{"mcp_server_id": "c4d5e6f7-...", "tool_name": "*"}'
```

## Step 3: Make a tool call through the gateway

All tool calls go to `POST /api/v1/proxy/tool-call`. You specify which MCP server to route to via the `X-MCP-Server` header (the name you used when registering the server).

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

```python
import httpx

NEXUS_URL = "http://localhost:8000/api/v1"
API_KEY = "nxai_..."

def call_tool(server: str, tool: str, arguments: dict, session_id: str | None = None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-MCP-Server": server,
        "Content-Type": "application/json",
    }
    if session_id:
        headers["X-NexusAI-Session-ID"] = session_id

    response = httpx.post(
        f"{NEXUS_URL}/proxy/tool-call",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
    )
    response.raise_for_status()
    return response.json()

result = call_tool("filesystem", "read_file", {"path": "/src/main.py"})
```

## How `{{SECRET_NAME}}` vault injection works

When the proxy receives a tool call, it scans `params.arguments` for strings that match the pattern `{{SECRET_NAME}}`. For each match, it:

1. Looks up `SECRET_NAME` in the vault, scoped to the calling agent
2. Decrypts the AES-256-GCM ciphertext using the master key
3. Replaces the placeholder with the decrypted value in-memory
4. Forwards the request to the upstream MCP server

The plaintext value is never written to disk, never logged, and never returned to the agent.

**Example**: If you store a secret named `GITHUB_TOKEN`:

```bash
curl -s -X POST http://localhost:8000/api/v1/vault/secrets \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{"name": "GITHUB_TOKEN", "value": "ghp_actual_token_here"}'
```

Then call a tool using the placeholder:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "github_list_repos",
    "arguments": {
      "token": "{{GITHUB_TOKEN}}",
      "org": "my-org"
    }
  }
}
```

The upstream MCP server receives `"token": "ghp_actual_token_here"`. The agent's code never contains or transmits the raw token.

## Session IDs

`X-NexusAI-Session-ID` is an optional header. When you send it, all tool calls with the same session ID are grouped into a single session in the audit log, which makes it easier to trace a complete agent run.

```
Agent run starts → no session ID exists yet
First tool call  → omit X-NexusAI-Session-ID
                 → gateway creates a new session, returns session ID in response header
Subsequent calls → include X-NexusAI-Session-ID: <id from first response>
                 → all events attached to same session
```

Use sessions when:
- You want to see all tool calls from one agent "run" in the dashboard as a group
- You're debugging a multi-step agent workflow and need a coherent trace
- You need to audit a single user interaction across multiple tool calls

## Common integration patterns

### Claude with tool use

Claude does not natively speak MCP. The typical pattern is to define your tools as Claude function definitions, receive tool call requests from Claude, and forward them through NexusAI:

```python
import anthropic
import httpx

client = anthropic.Anthropic()
NEXUS_URL = "http://localhost:8000/api/v1"
API_KEY = "nxai_..."

tools = [
    {
        "name": "read_file",
        "description": "Read a file from the filesystem",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }
]

def run_tool_call(tool_name: str, tool_input: dict) -> str:
    resp = httpx.post(
        f"{NEXUS_URL}/proxy/tool-call",
        headers={"Authorization": f"Bearer {API_KEY}", "X-MCP-Server": "filesystem"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": tool_input},
        },
    )
    return str(resp.json().get("result", {}))

messages = [{"role": "user", "content": "Read /src/main.py and summarize it"}]

while True:
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        tools=tools,
        messages=messages,
    )
    if response.stop_reason == "end_turn":
        print(response.content[0].text)
        break
    for block in response.content:
        if block.type == "tool_use":
            result = run_tool_call(block.name, block.input)
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": block.id, "content": result}
            ]})
```

### OpenAI function calling

Same pattern: catch `finish_reason: "tool_calls"`, forward each call to NexusAI, return results.

```python
import openai, httpx

openai_client = openai.OpenAI()
NEXUS_URL = "http://localhost:8000/api/v1"
API_KEY = "nxai_..."

def dispatch_tool(name: str, args: dict, mcp_server: str) -> str:
    resp = httpx.post(
        f"{NEXUS_URL}/proxy/tool-call",
        headers={"Authorization": f"Bearer {API_KEY}", "X-MCP-Server": mcp_server},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": name, "arguments": args}},
    )
    return str(resp.json().get("result"))
```

### Custom script (no LLM)

If you're not using an LLM at all — just a script that needs to call MCP tools with secrets injected:

```python
import httpx

def nexus_call(tool: str, args: dict) -> dict:
    return httpx.post(
        "http://localhost:8000/api/v1/proxy/tool-call",
        headers={
            "Authorization": "Bearer nxai_...",
            "X-MCP-Server": "my-server",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
              "params": {"name": tool, "arguments": args}},
    ).json()

# SLACK_TOKEN is stored in the vault — never in this script
nexus_call("send_message", {
    "channel": "#alerts",
    "text": "Deployment complete",
    "token": "{{SLACK_TOKEN}}",
})
```
