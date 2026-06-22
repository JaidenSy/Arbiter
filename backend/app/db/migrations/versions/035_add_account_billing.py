"""Add account-level billing columns to users (org->account billing, phase 1)

Adds nullable account-owned billing fields to ``users`` so the paid tier can
live on the account instead of (only) the organization. Purely additive:

    * no column is dropped or renamed
    * ``plan_tier`` is NULLABLE — NULL means "this account has no account-level
      plan; fall back to the org's plan_tier" (the dual-read rule in
      ``effective_plan``). This guarantees identical behaviour on day one.

The org-level columns (``organizations.plan_tier`` / ``stripe_*``) are kept
through the transition and only deprecated in a later phase.

See: Org -> Account Billing Migration Plan (Phase 1).

Revision ID: 035
Revises: 034
Create Date: 2026-06-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "035"
down_revision: str | None = "034"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Account-level plan tier. NULLABLE on purpose: NULL = "no account plan,
    # inherit from org" so existing rows behave exactly as before.
    op.add_column(
        "users",
        sa.Column("plan_tier", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("stripe_customer_id", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("stripe_subscription_id", sa.Text(), nullable=True),
    )
    # Allow NULL (no account plan) OR one of the known tiers. Mirrors the
    # organizations.plan_tier constraint but tolerates NULL.
    op.create_check_constraint(
        "ck_users_plan_tier",
        "users",
        "plan_tier IS NULL OR plan_tier IN ('free', 'pro', 'enterprise')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_plan_tier", "users", type_="check")
    op.drop_column("users", "stripe_subscription_id")
    op.drop_column("users", "stripe_customer_id")
    op.drop_column("users", "plan_tier")
