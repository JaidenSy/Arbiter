"""Add agent_id to cache_entries: keep agent-secret responses agent-private

The cache key is computed over the pre-injection arguments, so a
``{{SECRET}}`` placeholder is identical for every agent in the org even when
it resolves to a different agent-scoped secret.  Agent B could therefore be
served a response that was produced with agent A's credential.

Entries for calls that reference vault placeholders now carry the calling
agent's id and are matched only by that agent (Redis, exact and semantic
tiers).  NULL means org-shared.

No purge is needed: every existing row gets agent_id = NULL.  Placeholder
calls now look up with agent_id set (a different hash and an
``agent_id = :id`` filter), so the old shared rows for such calls are
unreachable and age out through the normal TTL sweeper.  Placeholder-free
rows keep the same hash format and stay valid.

Revision ID: 036
Revises: 035
Create Date: 2026-10-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "036"
down_revision: str | None = "035"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "cache_entries",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_cache_entries_agent_id",
        "cache_entries",
        "agents",
        ["agent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_cache_entries_org_server_tool_agent",
        "cache_entries",
        ["org_id", "mcp_server_id", "tool_name", "agent_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_cache_entries_org_server_tool_agent", table_name="cache_entries")
    op.drop_constraint("fk_cache_entries_agent_id", "cache_entries", type_="foreignkey")
    op.drop_column("cache_entries", "agent_id")
