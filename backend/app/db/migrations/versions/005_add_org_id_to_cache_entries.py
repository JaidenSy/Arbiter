"""add_org_id_to_cache_entries

Revision ID: 005
Revises: 004
Create Date: 2026-05-14

Adds org_id (nullable FK → organizations) to cache_entries so that cached
responses are isolated per tenant.  Existing rows remain accessible until they
expire (they will be served to no org since org_id IS NULL will never match a
real org UUID).  New entries always carry org_id from the proxy agent context.

Also adds a composite index on (org_id, tool_name) used by the semantic search
candidate query to avoid full-table scans.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "cache_entries",
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_cache_entries_org_tool",
        "cache_entries",
        ["org_id", "tool_name"],
    )


def downgrade() -> None:
    op.drop_index("idx_cache_entries_org_tool", table_name="cache_entries")
    op.drop_column("cache_entries", "org_id")
