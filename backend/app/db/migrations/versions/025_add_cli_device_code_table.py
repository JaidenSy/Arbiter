"""Add cli_device_codes table for CLI device flow authorization

Revision ID: 025
Revises: 024
Create Date: 2026-06-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "025"
down_revision: str | None = "024"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "cli_device_codes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("device_code", sa.String(36), nullable=False),
        sa.Column("user_code", sa.String(20), nullable=False),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "org_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_unique_constraint(
        "uq_cli_device_codes_device_code",
        "cli_device_codes",
        ["device_code"],
    )
    op.create_unique_constraint(
        "uq_cli_device_codes_user_code",
        "cli_device_codes",
        ["user_code"],
    )
    op.create_index(
        "ix_cli_device_codes_device_code",
        "cli_device_codes",
        ["device_code"],
    )
    op.create_index(
        "ix_cli_device_codes_user_code",
        "cli_device_codes",
        ["user_code"],
    )
    op.create_index(
        "ix_cli_device_codes_status_expires_at",
        "cli_device_codes",
        ["status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cli_device_codes_status_expires_at", table_name="cli_device_codes")
    op.drop_index("ix_cli_device_codes_user_code", table_name="cli_device_codes")
    op.drop_index("ix_cli_device_codes_device_code", table_name="cli_device_codes")
    op.drop_table("cli_device_codes")
