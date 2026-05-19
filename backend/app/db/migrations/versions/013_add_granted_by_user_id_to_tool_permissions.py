"""add granted_by_user_id to tool_permissions

Revision ID: 013
Revises: 012
Create Date: 2026-05-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("tool_permissions")]
    if "granted_by_user_id" not in cols:
        op.add_column(
            "tool_permissions",
            sa.Column(
                "granted_by_user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns("tool_permissions")]
    if "granted_by_user_id" in cols:
        op.drop_column("tool_permissions", "granted_by_user_id")
