"""Add org_memberships: users can belong to multiple organizations

Memberships become the source of truth for org access and per-org roles.
users.org_id / users.role remain as the active-org projection (the org the
user currently has selected); they are kept in sync at the app layer.

Backfill: one membership per *active* user from their current org_id/role.
Soft-deleted users (removed members, GDPR-anonymized accounts) do not get a
membership: they no longer belong to any org.

Revision ID: 033
Revises: 032
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "033"
down_revision: str | None = "032"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "org_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="member"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "org_id", name="uq_org_memberships_user_org"),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_org_memberships_role"),
    )
    op.create_index("ix_org_memberships_user_id", "org_memberships", ["user_id"])
    op.create_index("ix_org_memberships_org_id", "org_memberships", ["org_id"])

    # Backfill from the current single-org world.  gen_random_uuid() is
    # built into PostgreSQL 13+.
    op.execute(
        """
        INSERT INTO org_memberships (id, user_id, org_id, role, created_at, updated_at)
        SELECT gen_random_uuid(), id, org_id, role, created_at, now()
        FROM users
        WHERE is_active = true
        """
    )


def downgrade() -> None:
    op.drop_index("ix_org_memberships_org_id", table_name="org_memberships")
    op.drop_index("ix_org_memberships_user_id", table_name="org_memberships")
    op.drop_table("org_memberships")
