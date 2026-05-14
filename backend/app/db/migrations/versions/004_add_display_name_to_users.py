"""add_display_name_to_users

Revision ID: 004
Revises: 003
Create Date: 2026-05-14

Adds a nullable display_name column to the users table.
SSO users default to their provider name; password users set it on the
account page.  Null means "not set — fall back to email prefix in the UI."
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "display_name")
