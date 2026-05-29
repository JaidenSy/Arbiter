"""Add created_by_user_id to agents table

Tracks which org member registered each agent so that agents can be
automatically deactivated when a member is removed from the org.

Revision ID: 020
Revises: 019
Create Date: 2026-05-29
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect

revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("agents")]

    if "created_by_user_id" not in cols:
        op.execute("""
            ALTER TABLE agents
            ADD COLUMN created_by_user_id UUID
                REFERENCES users(id) ON DELETE SET NULL
        """)
        op.execute("""
            CREATE INDEX IF NOT EXISTS ix_agents_created_by_user_id
            ON agents (created_by_user_id)
        """)


def downgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("agents")]
    if "created_by_user_id" in cols:
        op.execute("DROP INDEX IF EXISTS ix_agents_created_by_user_id")
        op.drop_column("agents", "created_by_user_id")
