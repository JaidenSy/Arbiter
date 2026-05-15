"""initial_schema

Revision ID: 001
Revises:
Create Date: 2026-03-10

Baseline migration that creates all Arbiter tables from scratch.
Matches the ORM models in app/db/models/.  Run ``alembic upgrade head``
against a fresh PostgreSQL database to initialise the schema.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create all tables in dependency order."""

    # ── agents ────────────────────────────────────────────────────────────────
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("api_key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── mcp_servers ───────────────────────────────────────────────────────────
    op.create_table(
        "mcp_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column(
            "cache_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("TRUE"),
            comment="Set False for side-effectful servers that must never serve cached responses",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── tool_permissions ──────────────────────────────────────────────────────
    op.create_table(
        "tool_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mcp_server_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("granted_by", sa.Text, nullable=True),
        sa.UniqueConstraint("agent_id", "mcp_server_id", "tool_name", name="uq_tool_permission"),
    )

    # ── sessions ──────────────────────────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    # ── session_events ────────────────────────────────────────────────────────
    op.create_table(
        "session_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mcp_server_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mcp_servers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("request_payload", postgresql.JSONB, nullable=False),
        sa.Column("response_payload", postgresql.JSONB, nullable=True),
        sa.Column("cache_hit", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ── cache_entries ─────────────────────────────────────────────────────────
    op.create_table(
        "cache_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("input_embedding", postgresql.JSONB, nullable=True),
        sa.Column("response_payload", postgresql.JSONB, nullable=False),
        sa.Column("hit_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tool_name", "input_hash", name="uq_cache_entry_tool_hash"),
    )

    # ── vault_secrets ─────────────────────────────────────────────────────────
    op.create_table(
        "vault_secrets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("ciphertext", sa.Text, nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("name", "agent_id", name="uq_vault_secret_name_agent"),
    )

    # ── Indexes ───────────────────────────────────────────────────────────────
    op.create_index(
        "idx_session_events_session_id", "session_events", ["session_id"]
    )
    op.create_index(
        "idx_session_events_occurred_at",
        "session_events",
        [sa.text("occurred_at DESC")],
    )
    op.create_index("idx_sessions_agent_id", "sessions", ["agent_id"])
    op.create_index("idx_tool_permissions_agent_id", "tool_permissions", ["agent_id"])
    op.create_index("idx_cache_entries_expires_at", "cache_entries", ["expires_at"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_index("idx_cache_entries_expires_at", table_name="cache_entries")
    op.drop_index("idx_tool_permissions_agent_id", table_name="tool_permissions")
    op.drop_index("idx_sessions_agent_id", table_name="sessions")
    op.drop_index("idx_session_events_occurred_at", table_name="session_events")
    op.drop_index("idx_session_events_session_id", table_name="session_events")
    op.drop_table("vault_secrets")
    op.drop_table("cache_entries")
    op.drop_table("session_events")
    op.drop_table("sessions")
    op.drop_table("tool_permissions")
    op.drop_table("mcp_servers")
    op.drop_table("agents")
