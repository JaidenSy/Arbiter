# @arbiterai/cli

Official CLI for [Arbiter](https://arbiterai.dev) — the developer-first MCP gateway with agent identity, tool-level access control, secrets vault, and full observability.

## Install

```bash
npm install -g @arbiterai/cli
```

Requires Node.js 18+.

## Quickstart

```bash
# Authenticate via browser (device flow)
arbiter login

# Create an agent and save the API key
arbiter agent create --name my-agent

# Grant the agent access to a tool on an MCP server
arbiter permissions grant --agent <agent-id> --server <server-name> --tool <tool-name>

# Store a secret scoped to the agent
arbiter vault set --agent <agent-id> --key OPENAI_API_KEY --value sk-...
```

## Command Reference

### `arbiter login`

Authenticate with Arbiter using the browser-based device flow. Opens a browser tab where you approve access, then stores the token locally at `~/.config/arbiter/config.json`.

### `arbiter logout`

Clear your local session. Does not revoke the token server-side.

### `arbiter status [--json]`

Show current auth state and gateway health.

| Flag | Description |
|------|-------------|
| `--json` | Output raw JSON |

### `arbiter agent create --name <name> [--json]`

Create a new agent. Prints the agent ID and a one-time API key — save it immediately.

| Flag | Description |
|------|-------------|
| `--name <name>` | Display name for the agent (required) |
| `--json` | Output raw JSON |

### `arbiter agent list [--json]`

List all agents in your org.

| Flag | Description |
|------|-------------|
| `--json` | Output raw JSON |

### `arbiter agent delete <id>`

Delete an agent by ID. Prompts for confirmation before proceeding.

### `arbiter permissions grant --agent <id> --server <name> --tool <tool> [--json]`

Grant a tool permission to an agent on a named MCP server. Use `*` as the tool name to allow all tools on that server.

| Flag | Description |
|------|-------------|
| `--agent <id>` | Agent ID (required) |
| `--server <name>` | MCP server name (required) |
| `--tool <tool>` | Tool name, or `*` for all tools (required) |
| `--json` | Output raw JSON |

### `arbiter permissions list --agent <id> [--json]`

List all permissions granted to an agent.

| Flag | Description |
|------|-------------|
| `--agent <id>` | Agent ID (required) |
| `--json` | Output raw JSON |

### `arbiter vault set --agent <id> --key <key> --value <value> [--json]`

Store a secret in the vault scoped to an agent. Key must match `[A-Za-z0-9_]+`.

To avoid the secret appearing in shell history, use:

```bash
read -s VAL && arbiter vault set --agent <id> --key MY_KEY --value "$VAL"
```

| Flag | Description |
|------|-------------|
| `--agent <id>` | Agent ID to scope the secret to (required) |
| `--key <key>` | Secret key name, e.g. `OPENAI_API_KEY` (required) |
| `--value <value>` | Secret value (required) |
| `--json` | Output raw JSON |

## Auth

Arbiter CLI uses the [OAuth 2.0 Device Authorization Grant](https://datatracker.ietf.org/doc/html/rfc8628) flow:

1. `arbiter login` calls the Arbiter API to initiate a device flow and prints a short code.
2. Your browser opens to `https://arbiterai.dev/cli-auth?code=<code>` where you approve access.
3. The CLI polls for the token (every 3 seconds, up to 15 minutes).
4. On success, the token and org ID are written to `~/.config/arbiter/config.json` (mode `0600`).

To target a self-hosted or staging instance:

```bash
arbiter --api-url https://your-instance.example.com login
```

Or set the environment variable:

```bash
export ARBITER_API_URL=https://your-instance.example.com
```

## License

AGPL-3.0-or-later
