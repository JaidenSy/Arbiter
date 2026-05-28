"""Add rate_limit_per_minute to agents table

Revision ID: 019
Revises: 018
Create Date: 2026-05-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "rate_limit_per_minute")
