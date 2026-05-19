"""add rate_limit_per_minute to tool_permissions

Revision ID: 006
Revises: 005
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tool_permissions",
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tool_permissions", "rate_limit_per_minute")
