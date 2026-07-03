-- NexusAI: Canonical database schema (v2, multi-tenancy)
-- Run once against a fresh PostgreSQL database, OR let Alembic manage it.
-- Tables are created in dependency order (no forward references).

-- ── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector for semantic cache (optional)

-- ── organizations ─────────────────────────────────────────────────────────────
-- Top-level multi-tenancy boundary.  All resources belong to exactly one org.
CREATE TABLE IF NOT EXISTS organizations (
    id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    TEXT        NOT NULL,
    slug                    TEXT        NOT NULL UNIQUE,        -- URL-safe, e.g. "acme-corp"
    plan_tier               TEXT        NOT NULL DEFAULT 'free'
                                        CHECK (plan_tier IN ('free', 'pro', 'enterprise')),
    is_active               BOOLEAN     NOT NULL DEFAULT TRUE,  -- soft-delete / org suspension
    stripe_customer_id      TEXT,                               -- NULL until billing activated
    stripe_subscription_id  TEXT,                               -- NULL until billing activated
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);

-- ── users ─────────────────────────────────────────────────────────────────────
-- Human operators who log in with email/password and receive a JWT.
-- NOT the same as agents; agents are programmatic API-key callers.
CREATE TABLE IF NOT EXISTS users (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           TEXT        NOT NULL UNIQUE,
    hashed_password TEXT        NOT NULL,       -- bcrypt hash (cost factor 12)
    role            TEXT        NOT NULL DEFAULT 'member'
                                CHECK (role IN ('owner', 'admin', 'member')),
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_org_id ON users(org_id);
CREATE INDEX IF NOT EXISTS idx_users_email  ON users(email);

-- ── refresh_tokens ────────────────────────────────────────────────────────────
-- Opaque 30-day tokens (format: rt_<64hex>).  Rotated on every use.
-- SHA-256 hash stored; raw token never persisted.
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT        NOT NULL UNIQUE,       -- SHA-256 of raw token
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id    ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at DESC);

-- ── agents ───────────────────────────────────────────────────────────────────
-- Represents an AI agent (Claude instance, automation, etc.) that is
-- permitted to make tool calls through the NexusAI proxy.
CREATE TABLE IF NOT EXISTS agents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            TEXT        NOT NULL,
    description     TEXT,
    api_key_hash    TEXT        NOT NULL UNIQUE,   -- SHA-256 of raw API key
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agents_org_id ON agents(org_id);

-- ── mcp_servers ──────────────────────────────────────────────────────────────
-- MCP-compliant servers that agents are allowed to call through the proxy.
CREATE TABLE IF NOT EXISTS mcp_servers (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            TEXT        NOT NULL,
    base_url        TEXT        NOT NULL,
    description     TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    cache_enabled   BOOLEAN     NOT NULL DEFAULT TRUE,  -- FALSE for side-effectful servers
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_mcp_server_name_per_org UNIQUE (org_id, name)
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_org_id ON mcp_servers(org_id);

-- ── tool_permissions ─────────────────────────────────────────────────────────
-- RBAC join table: which agent may call which tool on which MCP server.
-- org_id is denormalized here for fast org-scoped permission listing.
CREATE TABLE IF NOT EXISTS tool_permissions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id            UUID        NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    mcp_server_id       UUID        NOT NULL REFERENCES mcp_servers(id) ON DELETE CASCADE,
    tool_name           TEXT        NOT NULL,           -- e.g. "read_file", "*" for all
    granted_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    granted_by          TEXT,                           -- free-text approver (legacy)
    granted_by_user_id  UUID        REFERENCES users(id) ON DELETE SET NULL,  -- FK approver
    UNIQUE (agent_id, mcp_server_id, tool_name)
);

CREATE INDEX IF NOT EXISTS idx_tool_permissions_agent_id ON tool_permissions(agent_id);
CREATE INDEX IF NOT EXISTS idx_tool_permissions_org_id   ON tool_permissions(org_id);

-- ── sessions ─────────────────────────────────────────────────────────────────
-- A logical grouping of tool calls made by a single agent in one context window.
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    agent_id        UUID        NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    metadata        JSONB       NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sessions_agent_id ON sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_sessions_org_id   ON sessions(org_id);

-- ── session_events ────────────────────────────────────────────────────────────
-- Immutable audit log of every tool call proxied within a session.
-- org_id is denormalized for fast per-org audit queries without multi-hop joins.
CREATE TABLE IF NOT EXISTS session_events (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id           UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    session_id       UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    mcp_server_id    UUID        REFERENCES mcp_servers(id) ON DELETE SET NULL,
    tool_name        TEXT        NOT NULL,
    request_payload  JSONB       NOT NULL,
    response_payload JSONB,
    cache_hit        BOOLEAN     NOT NULL DEFAULT FALSE,
    duration_ms      INTEGER,
    error            TEXT,
    occurred_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_events_session_id  ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_session_events_occurred_at ON session_events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_events_org_id      ON session_events(org_id);

-- ── cache_entries ─────────────────────────────────────────────────────────────
-- Semantic cache: stores tool call results keyed by embedding similarity.
-- Cache is scoped per-org so orgs cannot read each other's cached responses.
CREATE TABLE IF NOT EXISTS cache_entries (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id           UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    tool_name        TEXT        NOT NULL,
    input_hash       TEXT        NOT NULL,           -- SHA-256 of canonical request JSON
    input_embedding  JSONB,                          -- float[] stored as JSON (or vector if pgvector)
    response_payload JSONB       NOT NULL,
    hit_count        INTEGER     NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at       TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_cache_entry_per_org UNIQUE (org_id, tool_name, input_hash)
);

CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at ON cache_entries(expires_at);
CREATE INDEX IF NOT EXISTS idx_cache_entries_org_id     ON cache_entries(org_id);

-- ── vault_secrets ─────────────────────────────────────────────────────────────
-- Encrypted secrets injected into MCP calls at proxy time.
-- Ciphertext is AES-256-GCM; key lives in VAULT_ENCRYPTION_KEY env var.
CREATE TABLE IF NOT EXISTS vault_secrets (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,           -- logical name, e.g. "GITHUB_TOKEN"
    ciphertext  TEXT        NOT NULL,
    agent_id    UUID        REFERENCES agents(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_vault_secret_name_agent_org UNIQUE (org_id, name, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_vault_secrets_org_id ON vault_secrets(org_id);

-- ── usage_events ──────────────────────────────────────────────────────────────
-- One row per org per calendar day; counters incremented via upsert.
CREATE TABLE IF NOT EXISTS usage_events (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_date      DATE        NOT NULL DEFAULT CURRENT_DATE,
    tool_calls      INTEGER     NOT NULL DEFAULT 0,
    cache_hits      INTEGER     NOT NULL DEFAULT 0,
    vault_reads     INTEGER     NOT NULL DEFAULT 0,
    agents_created  INTEGER     NOT NULL DEFAULT 0,
    UNIQUE (org_id, event_date)
);

CREATE INDEX IF NOT EXISTS idx_usage_events_org_id     ON usage_events(org_id);
CREATE INDEX IF NOT EXISTS idx_usage_events_event_date ON usage_events(event_date DESC);

-- ── social_accounts ────────────────────────────────────────────────────────────
-- Links a user to an OAuth2 identity from an external provider (Google, GitHub).
-- A user may have multiple social accounts (one per provider).
CREATE TABLE IF NOT EXISTS social_accounts (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    org_id           UUID        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    provider         TEXT        NOT NULL CHECK (provider IN ('google', 'github')),
    provider_user_id TEXT        NOT NULL,
    email            TEXT,
    name             TEXT,
    avatar_url       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, provider_user_id)
);

CREATE INDEX IF NOT EXISTS idx_social_accounts_user_id  ON social_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_social_accounts_provider ON social_accounts(provider, provider_user_id);
