"""add tool_permission_events audit table

Revision ID: 017
Revises: 016
Create Date: 2026-05-20
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import inspect, text

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "tool_permission_events" in inspect(bind).get_table_names():
        return

    op.execute(text("""
        CREATE TABLE tool_permission_events (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            org_id               UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            agent_id             UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            permission_id        UUID REFERENCES tool_permissions(id) ON DELETE SET NULL,
            mcp_server_id        UUID REFERENCES mcp_servers(id) ON DELETE SET NULL,
            tool_name            VARCHAR(255) NOT NULL,
            action               VARCHAR(20)  NOT NULL,
            performed_by         TEXT,
            performed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            changes              JSONB,
            occurred_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    op.execute(text(
        "CREATE INDEX ix_tool_permission_events_agent_id "
        "ON tool_permission_events (agent_id, occurred_at DESC)"
    ))
    op.execute(text(
        "CREATE INDEX ix_tool_permission_events_org_id "
        "ON tool_permission_events (org_id, occurred_at DESC)"
    ))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS tool_permission_events"))
