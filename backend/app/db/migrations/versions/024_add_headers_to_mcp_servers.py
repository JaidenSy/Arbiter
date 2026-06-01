"""Add headers JSONB column to mcp_servers

Revision ID: 024
Revises: 023
Create Date: 2026-05-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "024"
down_revision: str | None = "023"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "mcp_servers",
        sa.Column("headers", JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("mcp_servers", "headers")
