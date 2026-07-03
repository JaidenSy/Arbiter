"""backfill all columns skipped by no-op stubs 006-012

Revision ID: 016
Revises: 015
Create Date: 2026-05-19

The staging DB was at revision 005 when the duplicate-006 chaos occurred.
Migrations 006-012 were later re-added as no-op stubs so Alembic could
navigate the chain: but stubs do nothing, so every column those migrations
were supposed to add is absent from the DB.

This migration adds every missing column/index idempotently.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect, text

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | None = None
depends_on: str | None = None


def _cols(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    # ── 006: rate_limit_per_minute on tool_permissions ────────────────────────
    if "rate_limit_per_minute" not in _cols("tool_permissions"):
        op.execute(text(
            "ALTER TABLE tool_permissions ADD COLUMN rate_limit_per_minute INTEGER"
        ))

    # ── 007: cache_ttl_seconds on tool_permissions ────────────────────────────
    if "cache_ttl_seconds" not in _cols("tool_permissions"):
        op.execute(text(
            "ALTER TABLE tool_permissions ADD COLUMN cache_ttl_seconds INTEGER"
        ))

    # ── 008: scope on agents ─────────────────────────────────────────────────
    if "scope" not in _cols("agents"):
        op.execute(text(
            "ALTER TABLE agents ADD COLUMN scope VARCHAR(32) NOT NULL DEFAULT 'full'"
        ))

    # ── 009: org_id on sessions and session_events ────────────────────────────
    if "org_id" not in _cols("sessions"):
        op.execute(text(
            "ALTER TABLE sessions "
            "ADD COLUMN org_id UUID REFERENCES organizations(id) ON DELETE CASCADE"
        ))
    if "org_id" not in _cols("session_events"):
        op.execute(text(
            "ALTER TABLE session_events "
            "ADD COLUMN org_id UUID REFERENCES organizations(id) ON DELETE CASCADE"
        ))

    # ── 010: composite index on session_events(org_id, occurred_at) ───────────
    if "ix_session_events_org_occurred" not in _indexes("session_events"):
        op.execute(text(
            "CREATE INDEX ix_session_events_org_occurred "
            "ON session_events (org_id, occurred_at)"
        ))

    # ── 011: is_verified on users ─────────────────────────────────────────────
    if "is_verified" not in _cols("users"):
        op.execute(text(
            "ALTER TABLE users "
            "ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT FALSE"
        ))

    # ── 012: org_invites table ────────────────────────────────────────────────
    bind = op.get_bind()
    existing_tables = inspect(bind).get_table_names()
    if "org_invites" not in existing_tables:
        op.execute(text("""
            CREATE TABLE org_invites (
                id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                org_id              UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                invited_by_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                email               VARCHAR(254) NOT NULL,
                role                VARCHAR(20) NOT NULL DEFAULT 'member',
                token               VARCHAR(128) NOT NULL UNIQUE,
                expires_at          TIMESTAMPTZ NOT NULL,
                accepted_at         TIMESTAMPTZ,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """))
        op.execute(text("CREATE INDEX ix_org_invites_token ON org_invites (token)"))
        op.execute(text("CREATE INDEX ix_org_invites_org_id ON org_invites (org_id)"))


def downgrade() -> None:
    pass  # not reversible: columns may have data
