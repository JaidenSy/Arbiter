"""Add mcp_server_id to cache_entries: scope cache hits per MCP server

Two MCP servers in the same org can expose tools with identical names
("search", "query", ...).  Cache keys previously spanned only
(org_id, tool_name, input_hash), so one server's cached response could be
served for another server's call.  Entries are now scoped per server and the
exact-match hash folds in org id + server id.

All existing rows are purged: the hash scheme changed, so no old entry can
ever match a new lookup: leaving them would only accumulate dead rows.

Revision ID: 032
Revises: 031
Create Date: 2026-06-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "032"
down_revision: str | None = "031"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("DELETE FROM cache_entries")
    op.add_column(
        "cache_entries",
        sa.Column("mcp_server_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_cache_entries_mcp_server_id",
        "cache_entries",
        "mcp_servers",
        ["mcp_server_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_cache_entries_org_server_tool",
        "cache_entries",
        ["org_id", "mcp_server_id", "tool_name"],
    )


def downgrade() -> None:
    op.drop_index("idx_cache_entries_org_server_tool", table_name="cache_entries")
    op.drop_constraint("fk_cache_entries_mcp_server_id", "cache_entries", type_="foreignkey")
    op.drop_column("cache_entries", "mcp_server_id")
