# Copyright (c) 2026 Jaiden Sy. All rights reserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Arbiter — OrgService: organization + membership lifecycle helpers.

Memberships (org_memberships) are the source of truth for which orgs a user
belongs to and their role in each.  ``users.org_id`` / ``users.role`` are a
denormalized projection of the user's *active* membership; every mutation
path in this module keeps the projection in sync.

Billing principle: plans and subscriptions attach to organizations, never to
memberships — joining or leaving an org has no billing effect.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org_membership import OrgMembership
from app.db.models.organization import Organization
from app.db.models.user import User

# ── Slug helpers ──────────────────────────────────────────────────────────────


def slugify(text: str) -> str:
    """
    Convert a human-readable name to a URL-safe slug.

    Example: "Acme Corp!" → "acme-corp"
    """
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "org"


async def _unique_slug(db: AsyncSession, name: str) -> str:
    """Return a slug for ``name`` that is not yet taken, suffixing -1, -2, ..."""
    slug = slugify(name)
    base_slug = slug
    counter = 1
    while await db.scalar(select(Organization).where(Organization.slug == slug)):
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


# ── Org / membership creation ─────────────────────────────────────────────────


async def create_org(db: AsyncSession, name: str) -> Organization:
    """
    Create a new free-tier organization with a unique slug.

    Flushes so ``org.id`` is populated; does not commit.
    """
    org = Organization(
        name=name,
        slug=await _unique_slug(db, name),
        plan_tier="free",
        is_active=True,
    )
    db.add(org)
    await db.flush()
    return org


async def add_membership(
    db: AsyncSession,
    *,
    user: User,
    org_id: uuid.UUID,
    role: str,
    set_active: bool = False,
) -> OrgMembership:
    """
    Add a membership row for ``user`` in ``org_id``.

    Args:
        set_active: When True, also point the user's active-org projection
                    (users.org_id / users.role) at this membership.

    Flushes so the row is queryable; does not commit.
    """
    membership = OrgMembership(user_id=user.id, org_id=org_id, role=role)
    db.add(membership)
    await db.flush()
    if set_active:
        set_active_membership(user, membership)
    return membership


def set_active_membership(user: User, membership: OrgMembership) -> None:
    """Point the user's active-org projection at ``membership``."""
    user.org_id = membership.org_id
    user.role = membership.role


# ── Membership queries ────────────────────────────────────────────────────────


async def get_membership(
    db: AsyncSession, user_id: uuid.UUID, org_id: uuid.UUID
) -> OrgMembership | None:
    """Return the membership of ``user_id`` in ``org_id``, or None."""
    return await db.scalar(
        select(OrgMembership).where(
            OrgMembership.user_id == user_id,
            OrgMembership.org_id == org_id,
        )
    )


async def list_memberships(db: AsyncSession, user_id: uuid.UUID) -> list[OrgMembership]:
    """Return all memberships of ``user_id``, oldest first."""
    result = await db.execute(
        select(OrgMembership)
        .where(OrgMembership.user_id == user_id)
        .order_by(OrgMembership.created_at.asc())
    )
    return list(result.scalars().all())


async def count_other_owners(
    db: AsyncSession, org_id: uuid.UUID, excluding_user_id: uuid.UUID
) -> int:
    """
    Count active owners of ``org_id`` other than ``excluding_user_id``.

    Zero means ``excluding_user_id`` is the sole owner (or the org has no
    owners at all) — the org cannot survive their departure unchanged.
    """
    return (
        await db.scalar(
            select(func.count(OrgMembership.id))
            .join(User, User.id == OrgMembership.user_id)
            .where(
                OrgMembership.org_id == org_id,
                OrgMembership.role == "owner",
                OrgMembership.user_id != excluding_user_id,
                User.is_active.is_(True),
            )
        )
        or 0
    )


# ── Active-org repointing ─────────────────────────────────────────────────────


async def repoint_active_org(db: AsyncSession, user: User) -> OrgMembership:
    """
    Give ``user`` a valid active org after losing their current one.

    Picks their most recently joined remaining membership; if none remain,
    creates a fresh personal free org (so an account is never org-less —
    the pre-membership model permanently bricked removed members).

    Flushes; does not commit.
    """
    remaining = await db.scalar(
        select(OrgMembership)
        .where(OrgMembership.user_id == user.id)
        .order_by(OrgMembership.created_at.desc())
        .limit(1)
    )
    if remaining is not None:
        set_active_membership(user, remaining)
        return remaining

    personal_name = f"{user.display_name or user.email.split('@')[0]}'s Org"
    org = await create_org(db, personal_name)
    return await add_membership(db, user=user, org_id=org.id, role="owner", set_active=True)
