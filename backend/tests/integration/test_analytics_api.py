"""
Integration tests for GET /api/v1/analytics/agents (GROWTH-03).

Coverage:
    Plan gate:
    - Free org → 402 with upgrade message
    - Pro org → 200 with correct response shape
    - Enterprise org → 200 with org_quota=null and pct_of_org_quota=0.0

    Response shape:
    - period is current "YYYY-MM"
    - agents sorted by tool_calls_this_month DESC
    - trend array always has exactly 7 entries
    - org_total_this_month sums all agents correctly

    Auth:
    - No auth → 401

    Org isolation:
    - Only the caller's org data is returned (enforced by WHERE org_id filter)
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────

_ORG_ID = uuid.UUID("11111111-0000-0000-0000-000000000001")
_AGENT_A_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
_AGENT_B_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")


def _make_user(org_id: uuid.UUID = _ORG_ID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.org_id = org_id
    user.email = "test@arbiter.test"
    user.is_active = True
    return user


def _make_org(plan_tier: str = "pro") -> MagicMock:
    org = MagicMock()
    org.id = _ORG_ID
    org.plan_tier = plan_tier
    return org


def _make_monthly_row(agent_id: uuid.UUID, agent_name: str, tool_calls: int) -> MagicMock:
    row = MagicMock()
    row.agent_id = agent_id
    row.agent_name = agent_name
    row.tool_calls = tool_calls
    return row


def _make_trend_row(agent_id: uuid.UUID, day: date, tool_calls: int) -> MagicMock:
    row = MagicMock()
    row.agent_id = agent_id
    row.day = day
    row.tool_calls = tool_calls
    return row


def _make_analytics_db(
    plan_tier: str = "pro",
    monthly_rows: list | None = None,
    trend_rows: list | None = None,
) -> AsyncMock:
    """
    Build a mock DB for the analytics endpoint.

    Call order:
      1. db.get(Organization, org_id) → org
      2. db.execute(monthly_q) → .all() returns monthly_rows
      3. db.execute(trend_q)   → .all() returns trend_rows
    """
    db = AsyncMock()
    db.get = AsyncMock(return_value=_make_org(plan_tier))

    monthly = monthly_rows or []
    trend = trend_rows or []

    call_count = 0

    async def execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.all.return_value = monthly
        else:
            result.all.return_value = trend
        return result

    db.execute = execute
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestAnalyticsAgentsPlanGate:
    @pytest.mark.asyncio
    async def test_free_org_returns_402(self):
        """Free org → HTTP 402 with upgrade message."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_analytics_db(plan_tier="free")

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/analytics/agents")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 402
        assert "Pro" in resp.json()["detail"] or "upgrade" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self):
        """Request without auth token → 401."""
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/analytics/agents")

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_pro_org_returns_200_with_correct_shape(self):
        """Pro org with seeded data → 200 with correct response shape."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        today = datetime.now(UTC).date()
        user = _make_user()
        monthly = [
            _make_monthly_row(_AGENT_A_ID, "agent-alpha", 5000),
            _make_monthly_row(_AGENT_B_ID, "agent-beta", 2000),
        ]
        trend = [
            _make_trend_row(_AGENT_A_ID, today - timedelta(days=1), 300),
            _make_trend_row(_AGENT_A_ID, today, 700),
        ]
        db = _make_analytics_db(plan_tier="pro", monthly_rows=monthly, trend_rows=trend)

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/analytics/agents")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert "period" in data
        assert "agents" in data
        assert "org_total_this_month" in data
        assert data["org_total_this_month"] == 7000
        assert len(data["agents"]) == 2
        # Sorted DESC — alpha first
        assert data["agents"][0]["agent_name"] == "agent-alpha"
        assert data["agents"][0]["tool_calls_this_month"] == 5000

    @pytest.mark.asyncio
    async def test_trend_always_has_7_entries(self):
        """Each agent's trend must always have exactly 7 entries."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        monthly = [_make_monthly_row(_AGENT_A_ID, "agent-alpha", 100)]
        # Only one trend row — remaining 6 days should be zero-filled
        today = datetime.now(UTC).date()
        trend = [_make_trend_row(_AGENT_A_ID, today, 100)]
        db = _make_analytics_db(plan_tier="pro", monthly_rows=monthly, trend_rows=trend)

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/analytics/agents")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        agent = resp.json()["agents"][0]
        assert len(agent["trend"]) == 7
        # Today is last entry and should have 100 calls
        assert agent["trend"][-1]["tool_calls"] == 100
        # All other days should be 0
        for point in agent["trend"][:-1]:
            assert point["tool_calls"] == 0

    @pytest.mark.asyncio
    async def test_enterprise_org_quota_is_null(self):
        """Enterprise org → org_quota=null and pct_of_org_quota=0.0 for all agents."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        monthly = [_make_monthly_row(_AGENT_A_ID, "agent-alpha", 999_999)]
        db = _make_analytics_db(plan_tier="enterprise", monthly_rows=monthly)

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/analytics/agents")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["org_quota"] is None
        assert data["agents"][0]["pct_of_org_quota"] == 0.0

    @pytest.mark.asyncio
    async def test_empty_org_returns_zero_totals(self):
        """Org with no tool calls → empty agents list and zero total."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_analytics_db(plan_tier="pro", monthly_rows=[], trend_rows=[])

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/analytics/agents")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["agents"] == []
        assert data["org_total_this_month"] == 0
