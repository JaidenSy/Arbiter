"""Add vault_audit_events — structured audit trail for vault secret operations

One row per operation (create, read/reveal, delete, rotate).  The secret_id
FK is SET NULL on secret deletion so the audit row survives the secret being
removed.  The user_id FK is also SET NULL to survive account deletion.

Revision ID: 034
Revises: 033
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "034"
down_revision: str | None = "033"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE TYPE vault_operation AS ENUM ('create', 'read', 'delete', 'rotate')")

    op.create_table(
        "vault_audit_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "secret_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vault_secrets.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "operation",
            sa.Enum(
                "create", "read", "delete", "rotate", name="vault_operation", create_type=False
            ),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("vault_audit_events")
    op.execute("DROP TYPE IF EXISTS vault_operation")
