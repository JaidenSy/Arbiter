"""Add gdpr_deletion_logs table

Revision ID: 021
Revises: 020
Create Date: 2026-05-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "gdpr_deletion_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "org_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("was_sole_owner", sa.Boolean(), nullable=False),
        sa.Column("had_stripe_subscription", sa.Boolean(), nullable=False),
    )
    op.create_index(
        "ix_gdpr_deletion_logs_deleted_at",
        "gdpr_deletion_logs",
        ["deleted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_gdpr_deletion_logs_deleted_at", table_name="gdpr_deletion_logs")
    op.drop_table("gdpr_deletion_logs")
