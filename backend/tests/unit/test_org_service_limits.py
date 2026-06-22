"""
Unit tests for org_service ownership-cap helpers (the abuse floor):

    count_owned_orgs       : coalesces NULL count to 0
    user_owns_paid_org     : truthiness from the COUNT(*) scalar
    owned_org_limit_for_user: tiers free vs paid ceiling

These exercise the query helpers directly with a mocked AsyncSession so the
free/paid tiering logic is covered without a live DB.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

from app.core.config import settings
from app.services.org import org_service


async def test_count_owned_orgs_coalesces_none_to_zero():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    assert await org_service.count_owned_orgs(db, uuid.uuid4()) == 0


async def test_user_owns_paid_org_truthiness():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=0)
    assert await org_service.user_owns_paid_org(db, uuid.uuid4()) is False

    db.scalar = AsyncMock(return_value=2)
    assert await org_service.user_owns_paid_org(db, uuid.uuid4()) is True


async def test_owned_org_limit_is_free_when_no_paid_org():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=0)  # user_owns_paid_org → False
    assert (
        await org_service.owned_org_limit_for_user(db, uuid.uuid4())
        == settings.free_owned_org_limit
    )


async def test_owned_org_limit_is_paid_when_owns_paid_org():
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=1)  # user_owns_paid_org → True
    assert (
        await org_service.owned_org_limit_for_user(db, uuid.uuid4())
        == settings.paid_owned_org_limit
    )
