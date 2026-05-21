"""Squashed baseline — full schema as of 2026-05-19

Revision ID: 013
Revises:
Create Date: 2026-05-19

Replaces individual migrations 001–013 with a single idempotent baseline.
Every DDL statement uses IF NOT EXISTS / DO-EXCEPTION so it is safe to run
against a fresh database AND against an existing one that was built by the
old migration chain.

Existing Railway/Vercel deployments already have alembic_version = '013',
so Alembic will see the DB is at head and skip this migration entirely.
Fresh deployments get the full schema in one shot.
"""

from __future__ import annotations

from alembic import op

# revision identifiers
revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | None = None
depends_on: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_col_if_missing(table: str, col_def: str) -> None:
    """ALTER TABLE … ADD COLUMN IF NOT EXISTS …"""
    op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_def}")


def _add_constraint_if_missing(ddl: str) -> None:
    """Wrap a constraint DDL in a DO-block that ignores already-exists errors.

    Catches both duplicate_object (42710) for named constraints and
    duplicate_table (42P07) which PostgreSQL raises when a UNIQUE constraint's
    backing index already exists independently.
    """
    op.execute(f"""
        DO $$ BEGIN
            {ddl};
        EXCEPTION
            WHEN duplicate_object THEN NULL;
            WHEN duplicate_table  THEN NULL;
        END $$;
    """)


def _create_index_if_missing(name: str, table: str, cols: str, extra: str = "") -> None:
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols}) {extra}".rstrip()
    )


# ---------------------------------------------------------------------------
# Upgrade — idempotent full schema
# ---------------------------------------------------------------------------

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ── organizations ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name            VARCHAR(255) NOT NULL,
            slug            VARCHAR(100) NOT NULL,
            plan_tier       VARCHAR(20)  NOT NULL DEFAULT 'free',
            is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
            stripe_customer_id      TEXT,
            stripe_subscription_id  TEXT,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    _add_constraint_if_missing(
        "ALTER TABLE organizations ADD CONSTRAINT ck_organizations_plan_tier "
        "CHECK (plan_tier IN ('free', 'pro', 'enterprise'))"
    )
    _add_constraint_if_missing(
        "ALTER TABLE organizations ADD CONSTRAINT uq_organizations_slug UNIQUE (slug)"
    )

    # ── users ────────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id          UUID NOT NULL,
            email           VARCHAR(254) NOT NULL,
            hashed_password VARCHAR(72)  NOT NULL DEFAULT '',
            role            VARCHAR(20)  NOT NULL DEFAULT 'member',
            is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
            display_name    VARCHAR(64),
            is_verified     BOOLEAN      NOT NULL DEFAULT FALSE,
            avatar_url      TEXT,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    _add_col_if_missing("users", "display_name VARCHAR(64)")
    _add_col_if_missing("users", "is_verified BOOLEAN NOT NULL DEFAULT FALSE")
    _add_col_if_missing("users", "avatar_url TEXT")
    _add_constraint_if_missing(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role "
        "CHECK (role IN ('owner', 'admin', 'member'))"
    )
    _add_constraint_if_missing(
        "ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE (email)"
    )
    _add_constraint_if_missing(
        "ALTER TABLE users ADD CONSTRAINT fk_users_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )

    # ── refresh_tokens ───────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID        NOT NULL,
            token_hash  VARCHAR(64) NOT NULL,
            expires_at  TIMESTAMPTZ NOT NULL,
            revoked     BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    _add_constraint_if_missing(
        "ALTER TABLE refresh_tokens ADD CONSTRAINT fk_refresh_tokens_user_id "
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE refresh_tokens ADD CONSTRAINT uq_refresh_tokens_token_hash "
        "UNIQUE (token_hash)"
    )

    # ── social_accounts ──────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS social_accounts (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id          UUID        NOT NULL,
            org_id           UUID        NOT NULL,
            provider         VARCHAR(20) NOT NULL,
            provider_user_id TEXT        NOT NULL,
            email            TEXT,
            name             TEXT,
            avatar_url       TEXT,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    _add_constraint_if_missing(
        "ALTER TABLE social_accounts ADD CONSTRAINT ck_social_accounts_provider "
        "CHECK (provider IN ('google', 'github'))"
    )
    _add_constraint_if_missing(
        "ALTER TABLE social_accounts ADD CONSTRAINT fk_social_accounts_user_id "
        "FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE social_accounts ADD CONSTRAINT fk_social_accounts_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )

    # ── usage_events ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS usage_events (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id          UUID NOT NULL,
            event_date      DATE NOT NULL DEFAULT CURRENT_DATE,
            tool_calls      INTEGER NOT NULL DEFAULT 0,
            cache_hits      INTEGER NOT NULL DEFAULT 0,
            vault_reads     INTEGER NOT NULL DEFAULT 0,
            agents_created  INTEGER NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    _add_constraint_if_missing(
        "ALTER TABLE usage_events ADD CONSTRAINT fk_usage_events_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE usage_events ADD CONSTRAINT uq_usage_events_org_date "
        "UNIQUE (org_id, event_date)"
    )

    # ── agents ───────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id       UUID,
            name         VARCHAR(255) NOT NULL,
            description  TEXT,
            api_key_hash VARCHAR(64)  NOT NULL,
            is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
            scope        VARCHAR(32)  NOT NULL DEFAULT 'full',
            created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    _add_col_if_missing("agents", "org_id UUID")
    _add_col_if_missing("agents", "scope VARCHAR(32) NOT NULL DEFAULT 'full'")
    _add_constraint_if_missing(
        "ALTER TABLE agents ADD CONSTRAINT fk_agents_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE agents ADD CONSTRAINT uq_agents_api_key_hash UNIQUE (api_key_hash)"
    )

    # ── mcp_servers ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS mcp_servers (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id       UUID,
            name         VARCHAR(255) NOT NULL,
            base_url     TEXT         NOT NULL,
            description  TEXT,
            is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
            cache_enabled BOOLEAN     NOT NULL DEFAULT TRUE,
            created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    _add_col_if_missing("mcp_servers", "org_id UUID")
    _add_constraint_if_missing(
        "ALTER TABLE mcp_servers ADD CONSTRAINT fk_mcp_servers_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE mcp_servers ADD CONSTRAINT uq_mcp_server_name_per_org "
        "UNIQUE (org_id, name)"
    )

    # ── tool_permissions ─────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS tool_permissions (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id               UUID NOT NULL,
            agent_id             UUID NOT NULL,
            mcp_server_id        UUID NOT NULL,
            tool_name            VARCHAR(255) NOT NULL,
            granted_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            granted_by           TEXT,
            granted_by_user_id   UUID,
            rate_limit_per_minute INTEGER,
            cache_ttl_seconds    INTEGER
        )
    """)
    _add_col_if_missing("tool_permissions", "org_id UUID")
    _add_col_if_missing("tool_permissions", "rate_limit_per_minute INTEGER")
    _add_col_if_missing("tool_permissions", "cache_ttl_seconds INTEGER")
    _add_col_if_missing("tool_permissions", "granted_by_user_id UUID")
    _add_constraint_if_missing(
        "ALTER TABLE tool_permissions ADD CONSTRAINT fk_tool_permissions_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE tool_permissions ADD CONSTRAINT fk_tool_permissions_agent_id "
        "FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE tool_permissions ADD CONSTRAINT fk_tool_permissions_mcp_server_id "
        "FOREIGN KEY (mcp_server_id) REFERENCES mcp_servers(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE tool_permissions ADD CONSTRAINT fk_tool_permissions_granted_by_user_id "
        "FOREIGN KEY (granted_by_user_id) REFERENCES users(id) ON DELETE SET NULL"
    )
    _add_constraint_if_missing(
        "ALTER TABLE tool_permissions ADD CONSTRAINT uq_tool_permission "
        "UNIQUE (agent_id, mcp_server_id, tool_name)"
    )

    # ── sessions ─────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_id    UUID        NOT NULL,
            org_id      UUID,
            started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            ended_at    TIMESTAMPTZ,
            metadata    JSONB       NOT NULL DEFAULT '{}'::jsonb
        )
    """)
    _add_col_if_missing("sessions", "org_id UUID")
    _add_constraint_if_missing(
        "ALTER TABLE sessions ADD CONSTRAINT fk_sessions_agent_id "
        "FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE sessions ADD CONSTRAINT fk_sessions_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )

    # ── session_events ────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS session_events (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id       UUID        NOT NULL,
            org_id           UUID,
            mcp_server_id    UUID,
            tool_name        VARCHAR(255) NOT NULL,
            request_payload  JSONB        NOT NULL,
            response_payload JSONB,
            cache_hit        BOOLEAN      NOT NULL DEFAULT FALSE,
            duration_ms      INTEGER,
            error            TEXT,
            occurred_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    _add_col_if_missing("session_events", "org_id UUID")
    _add_constraint_if_missing(
        "ALTER TABLE session_events ADD CONSTRAINT fk_session_events_session_id "
        "FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE session_events ADD CONSTRAINT fk_session_events_mcp_server_id "
        "FOREIGN KEY (mcp_server_id) REFERENCES mcp_servers(id) ON DELETE SET NULL"
    )
    _add_constraint_if_missing(
        "ALTER TABLE session_events ADD CONSTRAINT fk_session_events_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )

    # ── cache_entries ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS cache_entries (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id           UUID,
            tool_name        VARCHAR(255) NOT NULL,
            input_hash       VARCHAR(64)  NOT NULL,
            input_embedding  JSONB,
            response_payload JSONB        NOT NULL,
            hit_count        INTEGER      NOT NULL DEFAULT 0,
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
            expires_at       TIMESTAMPTZ  NOT NULL
        )
    """)
    _add_col_if_missing("cache_entries", "org_id UUID")
    _add_constraint_if_missing(
        "ALTER TABLE cache_entries ADD CONSTRAINT fk_cache_entries_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE cache_entries ADD CONSTRAINT uq_cache_entry_tool_hash "
        "UNIQUE (tool_name, input_hash)"
    )

    # ── vault_secrets ─────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS vault_secrets (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id      UUID,
            name        VARCHAR(255) NOT NULL,
            ciphertext  TEXT         NOT NULL,
            agent_id    UUID,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    _add_col_if_missing("vault_secrets", "org_id UUID")
    _add_constraint_if_missing(
        "ALTER TABLE vault_secrets ADD CONSTRAINT fk_vault_secrets_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE vault_secrets ADD CONSTRAINT fk_vault_secrets_agent_id "
        "FOREIGN KEY (agent_id) REFERENCES agents(id) ON DELETE SET NULL"
    )
    _add_constraint_if_missing(
        "ALTER TABLE vault_secrets ADD CONSTRAINT uq_vault_secret_name_agent_org "
        "UNIQUE (org_id, name, agent_id)"
    )

    # ── org_invites ───────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS org_invites (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id              UUID        NOT NULL,
            invited_by_user_id  UUID        NOT NULL,
            email               VARCHAR(254) NOT NULL,
            role                VARCHAR(20)  NOT NULL DEFAULT 'member',
            token               VARCHAR(128) NOT NULL,
            expires_at          TIMESTAMPTZ  NOT NULL,
            accepted_at         TIMESTAMPTZ,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """)
    _add_constraint_if_missing(
        "ALTER TABLE org_invites ADD CONSTRAINT fk_org_invites_org_id "
        "FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE org_invites ADD CONSTRAINT fk_org_invites_invited_by_user_id "
        "FOREIGN KEY (invited_by_user_id) REFERENCES users(id) ON DELETE CASCADE"
    )
    _add_constraint_if_missing(
        "ALTER TABLE org_invites ADD CONSTRAINT uq_org_invites_token UNIQUE (token)"
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    _create_index_if_missing("idx_session_events_session_id",  "session_events", "session_id")
    _create_index_if_missing("idx_session_events_occurred_at", "session_events", "occurred_at DESC")
    _create_index_if_missing("idx_sessions_agent_id",          "sessions",       "agent_id")
    _create_index_if_missing("idx_tool_permissions_agent_id",  "tool_permissions", "agent_id")
    _create_index_if_missing("idx_cache_entries_expires_at",   "cache_entries",  "expires_at")
    _create_index_if_missing("idx_cache_entries_org_tool",     "cache_entries",  "org_id, tool_name")
    _create_index_if_missing("ix_session_events_org_occurred", "session_events", "org_id, occurred_at")
    _create_index_if_missing("ix_org_invites_token",           "org_invites",    "token")
    _create_index_if_missing("ix_org_invites_org_id",          "org_invites",    "org_id")


# ---------------------------------------------------------------------------
# Downgrade — not supported for a squashed baseline
# ---------------------------------------------------------------------------

def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade is not supported for the squashed baseline migration. "
        "To reset, drop the database and re-run upgrade head."
    )
