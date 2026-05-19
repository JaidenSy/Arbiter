"""add scope to agents

Revision ID: 008
Revises: 007
Create Date: 2026-05-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "scope",
            sa.String(32),
            nullable=False,
            server_default="full",
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "scope")
