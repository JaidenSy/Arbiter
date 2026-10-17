"""Add tool_definitions + tool_change_policy: pin upstream tool definitions

Rug-pull defense (OWASP MCP03).  Each upstream tool's
{name, description, inputSchema} is hashed (canonical JSON) and pinned on
first sight.  A later tools/list with a different hash marks the tool
'changed' until an org admin re-approves it.

``tool_change_policy`` decides what happens to calls to a changed tool:
'allow' (default: call proceeds, warning logged, webhook fired) or 'block'.
It is set per org (organizations, NOT NULL, default 'allow') and can be
overridden per server (mcp_servers, NULL = inherit the org setting).

Revision ID: 037
Revises: 036
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "037"
down_revision: str | None = "036"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "tool_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mcp_server_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("approved_hash", sa.String(64), nullable=False),
        sa.Column("approved_definition", postgresql.JSONB(), nullable=False),
        sa.Column("current_hash", sa.String(64), nullable=False),
        sa.Column("current_definition", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("mcp_server_id", "tool_name", name="uq_tool_definitions_server_tool"),
        sa.CheckConstraint("status IN ('approved', 'changed')", name="ck_tool_definitions_status"),
    )
    op.create_index("ix_tool_definitions_org_status", "tool_definitions", ["org_id", "status"])

    op.add_column(
        "organizations",
        sa.Column("tool_change_policy", sa.String(10), nullable=False, server_default="allow"),
    )
    op.add_column(
        "mcp_servers",
        sa.Column("tool_change_policy", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("mcp_servers", "tool_change_policy")
    op.drop_column("organizations", "tool_change_policy")
    op.drop_index("ix_tool_definitions_org_status", table_name="tool_definitions")
    op.drop_table("tool_definitions")
