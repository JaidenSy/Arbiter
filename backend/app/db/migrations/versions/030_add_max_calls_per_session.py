"""add max_calls_per_session to agents

Revision ID: 030
Revises: 029
Create Date: 2026-06-10

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("max_calls_per_session", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "max_calls_per_session")
