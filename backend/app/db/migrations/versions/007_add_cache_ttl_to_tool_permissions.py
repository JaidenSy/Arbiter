"""add cache_ttl_seconds to tool_permissions

Revision ID: 007
Revises: 006
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tool_permissions",
        sa.Column("cache_ttl_seconds", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tool_permissions", "cache_ttl_seconds")
