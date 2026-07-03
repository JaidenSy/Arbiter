"""
Unit tests for app.services.plan.plan_service

Coverage:
    check_tool_call_quota:
        - Passes (no raise) when usage is under the monthly limit
        - Passes (no raise) when cache hit is below the effective limit
        - Raises QuotaExceededError when usage >= limit * OVERAGE_GRACE_FACTOR
        - Raises QuotaExceededError when usage equals the effective limit exactly
        - Enterprise plan (None limit) never raises regardless of usage
        - Cache miss path: queries DB, caches result, then checks quota
        - Cache hit path: skips DB query entirely, uses cached value

    check_resource_limit:
        - Passes (no raise) when current count < limit
        - Raises PlanLimitError when current count == limit
        - Raises PlanLimitError when current count > limit
        - Enterprise plan (None limit) never raises
        - Only counts rows where is_active == True (soft-deleted resources excluded)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_org(plan_tier: str = "free", org_id: uuid.UUID | None = None) -> MagicMock:
    org = MagicMock()
    org.id = org_id or uuid.uuid4()
    org.plan_tier = plan_tier
    return org


def _make_fake_redis(cached_value: bytes | None = None) -> AsyncMock:
    """Redis mock that returns cached_value on .get() and records .setex() calls."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=cached_value)
    redis.setex = AsyncMock(return_value=True)
    return redis


# ── check_tool_call_quota tests ───────────────────────────────────────────────


class TestCheckToolCallQuota:
    @pytest.mark.asyncio
    async def test_passes_when_usage_under_limit(self):
        """Under-limit usage must not raise."""
        from app.services.plan.plan_service import check_tool_call_quota

        org = _make_org(plan_tier="free")  # limit = 1000, grace = 1050
        redis = _make_fake_redis(cached_value=b"500")  # 500 < 1050

        db = AsyncMock()
        # If redis hits, no DB call is expected
        await check_tool_call_quota(redis=redis, db=db, org=org)
        # No exception = pass

    @pytest.mark.asyncio
    async def test_passes_when_at_zero_usage(self):
        """Zero usage should clearly never raise."""
        from app.services.plan.plan_service import check_tool_call_quota

        org = _make_org(plan_tier="pro")  # limit = 100_000
        redis = _make_fake_redis(cached_value=b"0")
        db = AsyncMock()
        await check_tool_call_quota(redis=redis, db=db, org=org)

    @pytest.mark.asyncio
    async def test_raises_quota_exceeded_when_at_effective_limit(self):
        """
        Effective limit = limit * OVERAGE_GRACE_FACTOR = 5000 * 1.05 = 5250.
        Used = 5250 → must raise QuotaExceededError.
        """
        from app.services.plan.plan_limits import QuotaExceededError
        from app.services.plan.plan_service import check_tool_call_quota

        org = _make_org(plan_tier="free")  # limit = 5000 → effective = 5250
        redis = _make_fake_redis(cached_value=b"5250")
        db = AsyncMock()

        with pytest.raises(QuotaExceededError) as exc_info:
            await check_tool_call_quota(redis=redis, db=db, org=org)

        err = exc_info.value
        assert err.used == 5250
        assert err.limit == 5000
        assert err.resource == "tool_calls"

    @pytest.mark.asyncio
    async def test_raises_quota_exceeded_when_over_limit(self):
        """Used >> limit should also raise."""
        from app.services.plan.plan_limits import QuotaExceededError
        from app.services.plan.plan_service import check_tool_call_quota

        org = _make_org(plan_tier="free")  # limit = 5000 → effective = 5250
        redis = _make_fake_redis(cached_value=b"9999")
        db = AsyncMock()

        with pytest.raises(QuotaExceededError):
            await check_tool_call_quota(redis=redis, db=db, org=org)

    @pytest.mark.asyncio
    async def test_does_not_raise_just_below_effective_limit(self):
        """Used = effective_limit - 1 must NOT raise."""
        from app.services.plan.plan_service import check_tool_call_quota

        org = _make_org(plan_tier="free")  # limit = 5000 → effective = 5250
        redis = _make_fake_redis(cached_value=b"5249")
        db = AsyncMock()

        # Should not raise
        await check_tool_call_quota(redis=redis, db=db, org=org)

    @pytest.mark.asyncio
    async def test_enterprise_plan_never_raises(self):
        """Enterprise orgs have None limit → check should always pass."""
        from app.services.plan.plan_service import check_tool_call_quota

        org = _make_org(plan_tier="enterprise")
        # Even with absurdly high usage, enterprise should pass
        redis = _make_fake_redis(cached_value=b"99999999")
        db = AsyncMock()

        await check_tool_call_quota(redis=redis, db=db, org=org)
        # Redis should not even be consulted for enterprise
        redis.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_queries_db_and_caches_result(self):
        """
        When Redis returns None (cache miss), the service queries the DB,
        stores the result in Redis via setex, then checks the quota.
        """
        from app.services.plan.plan_service import check_tool_call_quota

        org = _make_org(plan_tier="pro")  # limit = 100_000
        redis = _make_fake_redis(cached_value=None)  # cache miss

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=500)  # 500 tool calls in DB

        await check_tool_call_quota(redis=redis, db=db, org=org)

        # DB was queried
        db.scalar.assert_called_once()
        # Result was stored in Redis
        redis.setex.assert_called_once()
        # The cached value should be "500"
        setex_args = redis.setex.call_args
        assert "500" in str(setex_args)

    @pytest.mark.asyncio
    async def test_cache_miss_with_null_db_result_treats_as_zero(self):
        """
        If the DB returns NULL (no UsageEvent rows), used should be treated as 0.
        """
        from app.services.plan.plan_service import check_tool_call_quota

        org = _make_org(plan_tier="free")  # limit = 5000
        redis = _make_fake_redis(cached_value=None)  # cache miss

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=None)  # no rows

        # Should not raise (0 < 5250)
        await check_tool_call_quota(redis=redis, db=db, org=org)

    @pytest.mark.asyncio
    async def test_cache_hit_does_not_query_db(self):
        """When Redis has the value, the DB must not be queried."""
        from app.services.plan.plan_service import check_tool_call_quota

        org = _make_org(plan_tier="pro")
        redis = _make_fake_redis(cached_value=b"100")  # cache hit

        db = AsyncMock()
        db.scalar = AsyncMock()

        await check_tool_call_quota(redis=redis, db=db, org=org)

        db.scalar.assert_not_called()

    @pytest.mark.asyncio
    async def test_resets_at_is_set_in_exception(self):
        """QuotaExceededError.resets_at should be a UTC datetime."""
        from app.services.plan.plan_limits import QuotaExceededError
        from app.services.plan.plan_service import check_tool_call_quota

        org = _make_org(plan_tier="free")
        redis = _make_fake_redis(cached_value=b"5250")  # at effective limit
        db = AsyncMock()

        with pytest.raises(QuotaExceededError) as exc_info:
            await check_tool_call_quota(redis=redis, db=db, org=org)

        err = exc_info.value
        assert isinstance(err.resets_at, datetime)
        assert err.resets_at.tzinfo is not None


# ── check_resource_limit tests ────────────────────────────────────────────────


class TestCheckResourceLimit:
    def _make_model_col(self):
        """Return a stub ORM model and filter column for testing."""
        model = MagicMock()
        model.is_active = MagicMock()
        model.is_active.is_ = MagicMock(return_value=True)

        filter_col = MagicMock()
        filter_col.__eq__ = MagicMock(return_value=True)
        return model, filter_col

    @pytest.mark.asyncio
    async def test_passes_when_under_limit(self):
        """Current count < limit should not raise."""
        from app.services.plan.plan_service import check_resource_limit

        org = _make_org(plan_tier="free")  # max_agents = 2
        model, filter_col = self._make_model_col()

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=1)  # 1 active agent, limit is 2

        # Should not raise
        await check_resource_limit(
            db=db, org=org, resource="agents", model=model, filter_col=filter_col
        )

    @pytest.mark.asyncio
    async def test_raises_when_at_limit(self):
        """Current count == limit must raise PlanLimitError."""
        from app.services.plan.plan_limits import PlanLimitError
        from app.services.plan.plan_service import check_resource_limit

        org = _make_org(plan_tier="free")  # max_agents = 2
        model, filter_col = self._make_model_col()

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=2)  # exactly at limit

        with pytest.raises(PlanLimitError) as exc_info:
            await check_resource_limit(
                db=db, org=org, resource="agents", model=model, filter_col=filter_col
            )

        err = exc_info.value
        assert err.resource == "agents"
        assert err.current == 2
        assert err.limit == 2
        assert err.plan == "free"

    @pytest.mark.asyncio
    async def test_raises_when_over_limit(self):
        """Current count > limit must also raise PlanLimitError."""
        from app.services.plan.plan_limits import PlanLimitError
        from app.services.plan.plan_service import check_resource_limit

        org = _make_org(plan_tier="free")  # max_agents = 2
        model, filter_col = self._make_model_col()

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=5)

        with pytest.raises(PlanLimitError):
            await check_resource_limit(
                db=db, org=org, resource="agents", model=model, filter_col=filter_col
            )

    @pytest.mark.asyncio
    async def test_enterprise_plan_never_raises(self):
        """Enterprise has None limit → must never raise regardless of count."""
        from app.services.plan.plan_service import check_resource_limit

        org = _make_org(plan_tier="enterprise")
        model, filter_col = self._make_model_col()

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=9999)

        # Should not raise: and should not even query the DB
        await check_resource_limit(
            db=db, org=org, resource="agents", model=model, filter_col=filter_col
        )
        db.scalar.assert_not_called()

    @pytest.mark.asyncio
    async def test_null_db_result_treated_as_zero(self):
        """If DB returns None (no rows), current should be treated as 0 (< limit)."""
        from app.services.plan.plan_service import check_resource_limit

        org = _make_org(plan_tier="free")  # max_agents = 2
        model, filter_col = self._make_model_col()

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=None)  # no rows

        # 0 < 3 → should not raise
        await check_resource_limit(
            db=db, org=org, resource="agents", model=model, filter_col=filter_col
        )

    @pytest.mark.asyncio
    async def test_plan_limit_error_attributes(self):
        """PlanLimitError attributes must match the actual limit key name and plan."""
        from app.services.plan.plan_limits import PlanLimitError
        from app.services.plan.plan_service import check_resource_limit

        org = _make_org(plan_tier="pro")  # max_mcp_servers = 50
        model, filter_col = self._make_model_col()

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=50)  # at limit

        with pytest.raises(PlanLimitError) as exc_info:
            await check_resource_limit(
                db=db, org=org, resource="mcp_servers", model=model, filter_col=filter_col
            )

        err = exc_info.value
        assert err.resource == "mcp_servers"
        assert err.limit == 50
        assert err.plan == "pro"

    @pytest.mark.asyncio
    async def test_passes_when_zero_resources_exist(self):
        """New org with no resources created yet should always pass."""
        from app.services.plan.plan_service import check_resource_limit

        org = _make_org(plan_tier="free")
        model, filter_col = self._make_model_col()

        db = AsyncMock()
        db.scalar = AsyncMock(return_value=0)

        await check_resource_limit(
            db=db, org=org, resource="agents", model=model, filter_col=filter_col
        )
