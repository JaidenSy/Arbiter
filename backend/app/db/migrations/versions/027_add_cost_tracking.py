"""Add cost tracking: cost_per_call_usd on mcp_servers, cost_usd on session_events (#186)

Revision ID: 027
Revises: 026
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: str | None = "026"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "mcp_servers",
        sa.Column(
            "cost_per_call_usd",
            sa.Numeric(precision=10, scale=8),
            nullable=True,
            comment="Optional per-call cost in USD; NULL = no cost tracking for this server",
        ),
    )
    op.add_column(
        "session_events",
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=12, scale=6),
            nullable=True,
            comment="Cost of this call in USD; NULL = server has no cost configured or was a cache hit",
        ),
    )


def downgrade() -> None:
    op.drop_column("session_events", "cost_usd")
    op.drop_column("mcp_servers", "cost_per_call_usd")
