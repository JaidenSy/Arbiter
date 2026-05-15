# Vault

The Arbiter vault stores secrets for your agents — API keys, tokens, passwords — encrypted at rest using AES-256-GCM. Secrets are scoped per-agent: an agent cannot read or overwrite another agent's secrets, even if it knows the name.

## How it works

1. You write a secret via the API — a name/value pair tied to a specific agent.
2. Arbiter encrypts the value using AES-256-GCM with a 96-bit random nonce. The nonce is prepended to the ciphertext and stored together in the database. The plaintext is discarded.
3. In your tool call arguments, you reference the secret as `{{SECRET_NAME}}`.
4. At request time, the proxy scans `params.arguments` for `{{...}}` placeholders, decrypts each matched secret in-memory, substitutes the plaintext value, and forwards the request to the upstream MCP server.
5. The plaintext value never touches disk, never appears in logs, and is never returned to the calling agent.

## Encryption details

- **Algorithm**: AES-256-GCM (authenticated encryption — detects tampering)
- **Key size**: 256 bits (32 bytes), read from `VAULT_ENCRYPTION_KEY` environment variable as 64 hex characters
- **Nonce**: 96-bit random, generated fresh on every write, stored prepended to ciphertext
- **Storage**: Ciphertext in Postgres, plaintext never persisted
- **Key management**: Master key is environment-only — not in the database, not in config files

## Writing a secret

```bash
curl -s -X POST http://localhost:8000/api/v1/vault/secrets \
  -H "Authorization: Bearer nxai_..." \
  -H "Content-Type: application/json" \
  -d '{"name": "GITHUB_TOKEN", "value": "ghp_your_actual_token"}'
```

Response:

```json
{
  "name": "GITHUB_TOKEN",
  "agent_id": "3f7a1b2c-4d5e-6f7a-8b9c-0d1e2f3a4b5c",
  "created_at": "2026-04-01T12:00:00Z",
  "updated_at": "2026-04-01T12:00:00Z"
}
```

The response never includes the value. If you write a secret with the same name again, it overwrites the previous value (upsert).

```python
import httpx

httpx.post(
    "http://localhost:8000/api/v1/vault/secrets",
    headers={"Authorization": "Bearer nxai_..."},
    json={"name": "GITHUB_TOKEN", "value": "ghp_your_actual_token"},
)
```

## Using secrets in tool calls

Reference secrets in your tool call arguments using the `{{SECRET_NAME}}` placeholder syntax:

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

The upstream MCP server receives `"token": "ghp_your_actual_token"`. The agent code never contains or transmits the raw token.

Multiple secrets in one call are supported:

```json
{
  "params": {
    "name": "send_slack_message",
    "arguments": {
      "bot_token": "{{SLACK_BOT_TOKEN}}",
      "signing_secret": "{{SLACK_SIGNING_SECRET}}",
      "channel": "#alerts",
      "text": "Deploy complete"
    }
  }
}
```

## Per-agent isolation

Every secret is stored under `(name, agent_id)` — the combination is unique, not the name alone. This means:

- Agent A storing `GITHUB_TOKEN` and Agent B storing `GITHUB_TOKEN` are different secrets
- Agent A cannot read, overwrite, or enumerate Agent B's secrets
- An agent can only access secrets it created under its own API key

This isolation is enforced at the database query level, not just in application logic. The SQL `WHERE agent_id = $1` clause is always present on vault reads and writes.

## Listing secrets

```bash
curl -s http://localhost:8000/api/v1/vault/secrets \
  -H "Authorization: Bearer nxai_..."
```

Response includes names only — never values:

```json
[
  {"name": "GITHUB_TOKEN", "created_at": "2026-04-01T12:00:00Z"},
  {"name": "SLACK_BOT_TOKEN", "created_at": "2026-04-01T12:05:00Z"}
]
```

## Deleting a secret

```bash
curl -s -X DELETE http://localhost:8000/api/v1/vault/secrets/GITHUB_TOKEN \
  -H "Authorization: Bearer nxai_..."
```

After deletion, any tool call argument containing `{{GITHUB_TOKEN}}` will fail with a `400 Bad Request` — the placeholder cannot be resolved.

## Rotating the master key

The vault master key (`VAULT_ENCRYPTION_KEY`) is a 32-byte random key expressed as 64 hex characters. To rotate:

1. Generate a new key: `openssl rand -hex 32`
2. Re-encrypt all vault records using the new key (migration script provided in `infra/scripts/rotate-vault-key.py`)
3. Update `VAULT_ENCRYPTION_KEY` in your environment and restart the gateway

Key rotation does not require downtime if done in the correct order (re-encrypt first, swap env var second, restart third).

## Access control

**Writing secrets** (`POST /vault/secrets`, `DELETE /vault/secrets/{id}`) requires the `owner` or `admin` role.

**Listing secrets** (`GET /vault/secrets`) is available to all authenticated org members — it returns names only, never values.

**Reading a secret value** (`GET /vault/secrets/{id}`) requires the `owner` or `admin` role. Member-role users receive `403 Forbidden`. This prevents low-privilege org members from extracting credentials even if they have dashboard access.

The proxy reads secrets internally on behalf of the calling agent during tool call secret injection. This internal path bypasses the user-facing role check — it is enforced at the agent scope level instead (see [rbac.md](./rbac.md)).

## What the vault does not do

- Does not support secret versioning (planned for v2)
- Does not integrate with external secret stores (HashiCorp Vault, AWS Secrets Manager) — by design, to avoid external dependencies in the self-hosted setup
- Does not encrypt secret names, only values
- Does not support TTL-based secret expiry (planned for v2)
