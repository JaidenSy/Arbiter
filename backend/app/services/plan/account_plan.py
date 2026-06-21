# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
Arbiter — Account-level plan resolution (org->account billing, phase 1).

Today the paid tier lives on the *organization* (``organizations.plan_tier``).
The migration plan moves billing to the *account* (``users.plan_tier``) so that
an account's orgs are free workspaces that inherit the owner's plan, and quota is
aggregated per account rather than per org.

This module is the **single switch point** for that transition:

    effective_plan(db, org) -> the tier the rest of the app should enforce.

While ``settings.account_billing_enabled`` is False (the default, and the state
shipped in phase 1) ``effective_plan`` returns ``org.plan_tier`` verbatim — so
behaviour is byte-for-byte identical to the legacy code path. When the flag is
flipped, the effective tier becomes the **most generous** plan among the org's
own legacy ``plan_tier`` and its active owner accounts. Including the org's own
tier in that max is a deliberate transition-safety choice: an existing paid org
can never be *downgraded* by the cutover, even if the parity backfill has not yet
linked its owner account (the never-downgrade guarantee).

``backfill_account_plans`` is the grandfather step: it copies each paid org's
plan + Stripe linkage up onto its owner account, idempotently, never downgrading.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.org_membership import OrgMembership
from app.db.models.organization import Organization
from app.db.models.user import User
from app.services.plan.plan_limits import PAID_TIERS

logger = logging.getLogger(__name__)

# Ordering of tiers from least to most generous. Used to pick the "highest"
# plan among an org's owners. Unknown / NULL tiers rank below "free" so they can
# never win a max() and never silently grant access.
_PLAN_RANK: dict[str, int] = {"free": 0, "pro": 1, "enterprise": 2}


def plan_rank(tier: str | None) -> int:
    """Rank a tier for comparison; unknown or NULL ranks below every real tier."""
    if tier is None:
        return -1
    return _PLAN_RANK.get(tier, -1)


def higher_plan(a: str | None, b: str | None) -> str | None:
    """Return whichever of two tiers is more generous (None only if both None)."""
    return a if plan_rank(a) >= plan_rank(b) else b


async def _owner_account_tiers(db: AsyncSession, org_id) -> list[str]:
    """
    Account-level plan_tier of every *active owner* of ``org_id``.

    Mirrors the active-owner query used elsewhere (see
    ``org_service.count_other_owners``): role='owner' memberships joined to a
    User row that is active. NULL account tiers are filtered out — a user with
    no account plan contributes nothing to the org's effective plan.
    """
    rows = await db.scalars(
        select(User.plan_tier)
        .join(OrgMembership, OrgMembership.user_id == User.id)
        .where(
            OrgMembership.org_id == org_id,
            OrgMembership.role == "owner",
            User.is_active.is_(True),
            User.plan_tier.is_not(None),
        )
    )
    return [t for t in rows.all() if t is not None]


async def effective_plan(db: AsyncSession, org: Organization) -> str:
    """
    Resolve the plan tier the app should enforce for ``org``.

    Flag OFF (default / phase 1): returns ``org.plan_tier`` with **no** DB query,
    so it is a drop-in for the legacy ``org.plan_tier`` reads with identical
    behaviour and no added hot-path cost.

    Flag ON: returns the most generous tier among the org's own legacy
    ``plan_tier`` and its active owner accounts' ``plan_tier`` (never-downgrade).
    """
    if not settings.account_billing_enabled:
        return org.plan_tier

    owner_tiers = await _owner_account_tiers(db, org.id)
    if not owner_tiers:
        # No owner carries an account plan yet → legacy org plan governs.
        return org.plan_tier

    best = org.plan_tier
    for tier in owner_tiers:
        best = higher_plan(best, tier) or best
    return best


async def backfill_account_plans(db: AsyncSession) -> int:
    """
    Grandfather existing paid orgs onto their owner accounts (idempotent).

    For every org on a paid tier:
      * raise each *active owner's* account ``plan_tier`` to the org's tier
        (``higher_plan`` — never downgrades an account that is already higher);
      * attach the org's Stripe customer/subscription to its **earliest** active
        owner (the canonical billing owner), but only if that account has no
        Stripe linkage yet — so re-running never clobbers or duplicates a sub.

    Returns the number of accounts modified. Safe to run repeatedly; at launch
    the paid set is ~empty so this is a no-op, but it must be correct for the
    day a sub lands before the cutover. Caller is responsible for ``commit``.
    """
    paid_orgs = (
        await db.scalars(select(Organization).where(Organization.plan_tier.in_(PAID_TIERS)))
    ).all()

    updated_account_ids: set = set()

    for org in paid_orgs:
        owners = (
            await db.scalars(
                select(User)
                .join(OrgMembership, OrgMembership.user_id == User.id)
                .where(
                    OrgMembership.org_id == org.id,
                    OrgMembership.role == "owner",
                    User.is_active.is_(True),
                )
                .order_by(OrgMembership.created_at.asc())
            )
        ).all()

        if not owners:
            logger.warning(
                "backfill_account_plans: paid org %s (%s) has no active owner — "
                "skipped; cannot grandfather a plan onto a missing account",
                org.id,
                org.plan_tier,
            )
            continue

        # Plan label → every active owner (most-generous wins).
        for owner in owners:
            new_tier = higher_plan(owner.plan_tier, org.plan_tier)
            if new_tier != owner.plan_tier:
                owner.plan_tier = new_tier
                updated_account_ids.add(owner.id)

        # Stripe linkage → the single earliest owner, only if unset.
        billing_owner = owners[0]
        if org.stripe_customer_id and billing_owner.stripe_customer_id is None:
            billing_owner.stripe_customer_id = org.stripe_customer_id
            billing_owner.stripe_subscription_id = org.stripe_subscription_id
            updated_account_ids.add(billing_owner.id)

    if updated_account_ids:
        logger.info(
            "backfill_account_plans: grandfathered %d account(s) from %d paid org(s)",
            len(updated_account_ids),
            len(paid_orgs),
        )
    return len(updated_account_ids)
