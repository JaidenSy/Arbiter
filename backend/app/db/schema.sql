-- NexusAI — Canonical database schema
-- Run once against a fresh PostgreSQL database, OR let Alembic manage it.
-- Tables are created in dependency order (no forward references).

-- ── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector for semantic cache (optional)

-- ── agents ───────────────────────────────────────────────────────────────────
-- Represents an AI agent (Claude instance, automation, etc.) that is
-- permitted to make tool calls through the NexusAI proxy.
CREATE TABLE IF NOT EXISTS agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT        NOT NULL,
    description     TEXT,
    api_key_hash    TEXT        NOT NULL UNIQUE,   -- SHA-256 of raw API key
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── mcp_servers ──────────────────────────────────────────────────────────────
-- MCP-compliant servers that agents are allowed to call through the proxy.
CREATE TABLE IF NOT EXISTS mcp_servers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT        NOT NULL UNIQUE,
    base_url        TEXT        NOT NULL,
    description     TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    cache_enabled   BOOLEAN     NOT NULL DEFAULT TRUE,  -- FALSE for side-effectful servers
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── tool_permissions ─────────────────────────────────────────────────────────
-- RBAC join table: which agent may call which tool on which MCP server.
CREATE TABLE IF NOT EXISTS tool_permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID        NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    mcp_server_id   UUID        NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
    tool_name       TEXT        NOT NULL,           -- e.g. "read_file", "*" for all
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by      TEXT,                           -- human who approved this
    UNIQUE (agent_id, mcp_server_id, tool_name)
);

-- ── sessions ─────────────────────────────────────────────────────────────────
-- A logical grouping of tool calls made by a single agent in one context window.
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id        UUID        NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    metadata        JSONB       NOT NULL DEFAULT '{}'
);

-- ── session_events ────────────────────────────────────────────────────────────
-- Immutable audit log of every tool call proxied within a session.
CREATE TABLE IF NOT EXISTS session_events (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    mcp_server_id   UUID        REFERENCES mcp_servers(id) ON DELETE SET NULL,
    tool_name       TEXT        NOT NULL,
    request_payload JSONB       NOT NULL,
    response_payload JSONB,
    cache_hit       BOOLEAN     NOT NULL DEFAULT FALSE,
    duration_ms     INTEGER,
    error           TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── cache_entries ─────────────────────────────────────────────────────────────
-- Semantic cache: stores tool call results keyed by embedding similarity.
CREATE TABLE IF NOT EXISTS cache_entries (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_name       TEXT        NOT NULL,
    input_hash      TEXT        NOT NULL,           -- SHA-256 of canonical request JSON
    input_embedding JSONB,                          -- float[] stored as JSON (or vector if pgvector)
    response_payload JSONB      NOT NULL,
    hit_count       INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    UNIQUE (tool_name, input_hash)
);

-- ── vault_secrets ─────────────────────────────────────────────────────────────
-- Encrypted secrets injected into MCP calls at proxy time.
-- Ciphertext is AES-256-GCM; key lives in VAULT_ENCRYPTION_KEY env var.
CREATE TABLE IF NOT EXISTS vault_secrets (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT        NOT NULL,           -- logical name, e.g. "GITHUB_TOKEN"
    ciphertext      TEXT        NOT NULL,
    agent_id        UUID        REFERENCES agents(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, agent_id)                         -- per-agent namespace isolation
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_session_events_session_id  ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_session_events_occurred_at ON session_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_agent_id          ON sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_tool_permissions_agent_id  ON tool_permissions(agent_id);
CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at   ON cache_entries(expires_at);
