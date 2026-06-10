"""Add mcp_server_health_checks table for automated health monitoring (#208)

Revision ID: 026
Revises: 025
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "026"
down_revision: str | None = "025"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_server_health_checks",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "server_id",
            UUID(as_uuid=True),
            sa.ForeignKey("mcp_servers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("is_healthy", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "checked_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_mcp_server_health_checks_server_id", "mcp_server_health_checks", ["server_id"]
    )
    op.create_index("ix_mcp_server_health_checks_org_id", "mcp_server_health_checks", ["org_id"])
    op.create_index(
        "ix_mcp_server_health_checks_checked_at",
        "mcp_server_health_checks",
        ["server_id", "checked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_server_health_checks_checked_at", table_name="mcp_server_health_checks")
    op.drop_index("ix_mcp_server_health_checks_org_id", table_name="mcp_server_health_checks")
    op.drop_index("ix_mcp_server_health_checks_server_id", table_name="mcp_server_health_checks")
    op.drop_table("mcp_server_health_checks")
