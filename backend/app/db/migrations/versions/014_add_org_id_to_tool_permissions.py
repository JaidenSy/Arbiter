"""add org_id to tool_permissions

Revision ID: 014
Revises: 013
Create Date: 2026-05-19

tool_permissions.org_id exists in the ORM model but was never added by any
migration: it was only included in the squashed baseline (013) which existing
deployments skipped because their alembic_version was already at 013.

Uses IF NOT EXISTS so it is safe to re-run against any DB state.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("tool_permissions")]

    if "org_id" not in cols:
        op.execute("""
            ALTER TABLE tool_permissions
            ADD COLUMN org_id UUID REFERENCES organizations(id) ON DELETE CASCADE
        """)


def downgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("tool_permissions")]
    if "org_id" in cols:
        op.drop_column("tool_permissions", "org_id")
