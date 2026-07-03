"""
Unit tests for app.services.plan.account_plan (org->account billing, phase 1).

Coverage:
    plan_rank / higher_plan:
        - Tier ordering free < pro < enterprise; NULL/unknown ranks lowest
        - higher_plan picks the more generous tier

    effective_plan:
        - Flag OFF: returns org.plan_tier verbatim and never touches the DB
          (the phase-1 parity guarantee: drop-in for legacy org.plan_tier reads)
        - Flag ON, no owner carries an account plan: falls back to org.plan_tier
        - Flag ON, an owner account is Pro while the org is free: returns "pro"
        - Flag ON, multiple owners: returns the most generous (max) account plan
        - Flag ON, owner account is free but org is Pro: returns "pro"
          (never-downgrade: the org's legacy tier is included in the max)

    backfill_account_plans:
        - Grandfathers a paid org's plan + Stripe linkage onto its owner account
        - Idempotent: re-running over already-grandfathered data changes nothing
        - A paid org with no active owner is skipped (no crash, not counted)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_org(plan_tier="free", stripe_customer_id=None, stripe_subscription_id=None):
    org = MagicMock()
    org.id = uuid.uuid4()
    org.plan_tier = plan_tier
    org.stripe_customer_id = stripe_customer_id
    org.stripe_subscription_id = stripe_subscription_id
    return org


def _make_user(plan_tier=None, stripe_customer_id=None, stripe_subscription_id=None):
    user = MagicMock()
    user.id = uuid.uuid4()
    user.plan_tier = plan_tier
    user.stripe_customer_id = stripe_customer_id
    user.stripe_subscription_id = stripe_subscription_id
    return user


def _scalars(items):
    """Mock the object returned by ``await db.scalars(...)``: has a sync .all()."""
    res = MagicMock()
    res.all = MagicMock(return_value=items)
    return res


def _db_returning(*scalars_results):
    """An AsyncMock db whose successive .scalars() awaits yield the given results."""
    db = AsyncMock()
    db.scalars = AsyncMock(side_effect=list(scalars_results))
    return db


@pytest.fixture
def billing_on(monkeypatch):
    """Flip ACCOUNT_BILLING_ENABLED on for the duration of a test."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "account_billing_enabled", True)


@pytest.fixture
def billing_off(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "account_billing_enabled", False)


# ── plan_rank / higher_plan ───────────────────────────────────────────────────


class TestPlanRank:
    def test_tier_ordering(self):
        from app.services.plan.account_plan import plan_rank

        assert plan_rank("free") < plan_rank("pro") < plan_rank("enterprise")

    def test_null_and_unknown_rank_below_free(self):
        from app.services.plan.account_plan import plan_rank

        assert plan_rank(None) < plan_rank("free")
        assert plan_rank("bogus") < plan_rank("free")

    def test_higher_plan_picks_more_generous(self):
        from app.services.plan.account_plan import higher_plan

        assert higher_plan("free", "pro") == "pro"
        assert higher_plan("pro", "free") == "pro"
        assert higher_plan("enterprise", "pro") == "enterprise"
        assert higher_plan(None, "free") == "free"


# ── effective_plan ────────────────────────────────────────────────────────────


class TestEffectivePlan:
    @pytest.mark.asyncio
    async def test_flag_off_returns_org_plan_without_db(self, billing_off):
        from app.services.plan.account_plan import effective_plan

        org = _make_org(plan_tier="pro")
        db = AsyncMock()
        db.scalars = AsyncMock()

        assert await effective_plan(db, org) == "pro"
        db.scalars.assert_not_called()  # parity path must not hit the DB

    @pytest.mark.asyncio
    async def test_flag_off_free_org_stays_free(self, billing_off):
        from app.services.plan.account_plan import effective_plan

        org = _make_org(plan_tier="free")
        db = AsyncMock()
        db.scalars = AsyncMock()

        assert await effective_plan(db, org) == "free"
        db.scalars.assert_not_called()

    @pytest.mark.asyncio
    async def test_flag_on_no_account_plan_falls_back_to_org(self, billing_on):
        from app.services.plan.account_plan import effective_plan

        org = _make_org(plan_tier="free")
        db = _db_returning(_scalars([]))  # no owner carries an account plan

        assert await effective_plan(db, org) == "free"

    @pytest.mark.asyncio
    async def test_flag_on_owner_account_pro_beats_free_org(self, billing_on):
        from app.services.plan.account_plan import effective_plan

        org = _make_org(plan_tier="free")
        db = _db_returning(_scalars(["pro"]))

        assert await effective_plan(db, org) == "pro"

    @pytest.mark.asyncio
    async def test_flag_on_multiple_owners_takes_max(self, billing_on):
        from app.services.plan.account_plan import effective_plan

        org = _make_org(plan_tier="free")
        db = _db_returning(_scalars(["free", "enterprise", "pro"]))

        assert await effective_plan(db, org) == "enterprise"

    @pytest.mark.asyncio
    async def test_flag_on_never_downgrades_below_org_plan(self, billing_on):
        """Org is Pro but its owner account is only free → must stay Pro."""
        from app.services.plan.account_plan import effective_plan

        org = _make_org(plan_tier="pro")
        db = _db_returning(_scalars(["free"]))

        assert await effective_plan(db, org) == "pro"


# ── backfill_account_plans ────────────────────────────────────────────────────


class TestBackfill:
    @pytest.mark.asyncio
    async def test_grandfathers_plan_and_stripe_onto_owner(self):
        from app.services.plan.account_plan import backfill_account_plans

        org = _make_org(
            plan_tier="pro",
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )
        owner = _make_user(plan_tier=None, stripe_customer_id=None)

        # 1st scalars() → paid orgs; 2nd scalars() → that org's owners.
        db = _db_returning(_scalars([org]), _scalars([owner]))

        changed = await backfill_account_plans(db)

        assert changed == 1
        assert owner.plan_tier == "pro"
        assert owner.stripe_customer_id == "cus_123"
        assert owner.stripe_subscription_id == "sub_123"

    @pytest.mark.asyncio
    async def test_idempotent_no_change_when_already_grandfathered(self):
        from app.services.plan.account_plan import backfill_account_plans

        org = _make_org(
            plan_tier="pro",
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )
        # Owner already Pro with Stripe linkage: a second run must be a no-op.
        owner = _make_user(
            plan_tier="pro",
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )
        db = _db_returning(_scalars([org]), _scalars([owner]))

        changed = await backfill_account_plans(db)

        assert changed == 0
        assert owner.plan_tier == "pro"

    @pytest.mark.asyncio
    async def test_never_downgrades_a_higher_account(self):
        """Enterprise account owning a Pro org keeps enterprise."""
        from app.services.plan.account_plan import backfill_account_plans

        org = _make_org(plan_tier="pro")
        owner = _make_user(plan_tier="enterprise")
        db = _db_returning(_scalars([org]), _scalars([owner]))

        changed = await backfill_account_plans(db)

        assert changed == 0
        assert owner.plan_tier == "enterprise"

    @pytest.mark.asyncio
    async def test_paid_org_with_no_owner_is_skipped(self):
        from app.services.plan.account_plan import backfill_account_plans

        org = _make_org(plan_tier="pro", stripe_customer_id="cus_x")
        db = _db_returning(_scalars([org]), _scalars([]))  # no active owners

        changed = await backfill_account_plans(db)

        assert changed == 0  # nothing to grandfather, and no crash
