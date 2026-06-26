"""
Integration tests for GET /api/v1/agents/{id}/risk.

Uses httpx AsyncClient against the FastAPI app with mocked DB and fake Redis
(same pattern as test_billing_api.py: no live Postgres or Redis required).

Coverage:
    - 200 for a pro-plan org with zero activity → score=0.0, level="low"
    - 402 for a free-plan org (plan gate)
    - 404 when the agent does not belong to the org
    - 500 when db.get(Organization) returns None
    - Cache hit: second request returns from Redis without re-querying the DB
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_mock_user(org_id: uuid.UUID) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.org_id = org_id
    user.is_active = True
    user.email = "test@example.com"
    return user


def _make_mock_org(plan_tier: str = "pro", org_id: uuid.UUID | None = None) -> MagicMock:
    org = MagicMock()
    org.id = org_id or uuid.uuid4()
    org.plan_tier = plan_tier
    return org


def _make_stats_mock(data: dict) -> MagicMock:
    m = MagicMock()
    m.mappings.return_value.one.return_value = data
    return m


_ZERO_STATS = {
    "total_7d": 0,
    "total_24h": 0,
    "total_1h": 0,
    "errors_7d": 0,
    "errors_24h": 0,
    "avg_dur_7d": None,
    "avg_dur_24h": None,
    "off_hours_24h": 0,
}
_ZERO_NOVEL = {"novel_tool_count": 0}


# ── Fixture ───────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def risk_client(fake_redis) -> AsyncGenerator:
    """
    HTTPX test client with get_current_user and get_redis overridden.
    Yields (client, mock_user, org_id).  Per-test DB mocks are injected via
    app.dependency_overrides[get_db] inside each test.
    """
    from app.core.dependencies import get_current_user, get_redis
    from app.main import app

    org_id = uuid.uuid4()
    mock_user = _make_mock_user(org_id=org_id)

    async def override_get_current_user():
        return mock_user

    async def override_get_redis(request=None):
        return fake_redis

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, mock_user, org_id

    app.dependency_overrides.clear()


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestAgentRiskEndpoint:
    @pytest.mark.asyncio
    async def test_pro_plan_zero_activity_returns_score_0(self, risk_client):
        """Pro org with no session data gets score=0.0 and level='low'."""
        from app.core.dependencies import get_db
        from app.main import app

        client, mock_user, org_id = risk_client
        agent_id = uuid.uuid4()

        mock_org = _make_mock_org(plan_tier="pro", org_id=org_id)
        mock_agent_result = MagicMock()
        mock_agent_result.scalar_one_or_none.return_value = MagicMock(id=agent_id)

        async def override_get_db():
            db = AsyncMock()
            db.get = AsyncMock(return_value=mock_org)
            db.execute = AsyncMock(
                side_effect=[
                    mock_agent_result,
                    _make_stats_mock(_ZERO_STATS),
                    _make_stats_mock(_ZERO_NOVEL),
                ]
            )
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            r = await client.get(f"/api/v1/agents/{agent_id}/risk")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert r.status_code == 200
        body = r.json()
        assert body["score"] == 0.0
        assert body["level"] == "low"
        assert body["agent_id"] == str(agent_id)
        assert set(body["signals"].keys()) == {
            "error_rate_spike",
            "burst_ratio",
            "novel_tool_count",
            "latency_spike_ratio",
            "off_hours_ratio_24h",
        }

    @pytest.mark.asyncio
    async def test_free_plan_returns_402(self, risk_client):
        """Free-plan org gets 402 Payment Required."""
        from app.core.dependencies import get_db
        from app.main import app

        client, mock_user, org_id = risk_client
        agent_id = uuid.uuid4()

        mock_org = _make_mock_org(plan_tier="free", org_id=org_id)

        async def override_get_db():
            db = AsyncMock()
            db.get = AsyncMock(return_value=mock_org)
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            r = await client.get(f"/api/v1/agents/{agent_id}/risk")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert r.status_code == 402

    @pytest.mark.asyncio
    async def test_agent_not_found_returns_404(self, risk_client):
        """Agent that doesn't belong to the org returns 404."""
        from app.core.dependencies import get_db
        from app.main import app

        client, mock_user, org_id = risk_client
        agent_id = uuid.uuid4()

        mock_org = _make_mock_org(plan_tier="pro", org_id=org_id)
        mock_agent_result = MagicMock()
        mock_agent_result.scalar_one_or_none.return_value = None  # not found

        async def override_get_db():
            db = AsyncMock()
            db.get = AsyncMock(return_value=mock_org)
            db.execute = AsyncMock(return_value=mock_agent_result)
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            r = await client.get(f"/api/v1/agents/{agent_id}/risk")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_org_not_found_returns_500(self, risk_client):
        """Missing org record returns 500."""
        from app.core.dependencies import get_db
        from app.main import app

        client, mock_user, org_id = risk_client
        agent_id = uuid.uuid4()

        async def override_get_db():
            db = AsyncMock()
            db.get = AsyncMock(return_value=None)
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            r = await client.get(f"/api/v1/agents/{agent_id}/risk")
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert r.status_code == 500

    @pytest.mark.asyncio
    async def test_second_request_served_from_cache(self, risk_client, fake_redis):
        """Second call within TTL returns from Redis; DB execute is not called again."""
        from app.core.dependencies import get_db
        from app.main import app

        client, mock_user, org_id = risk_client
        agent_id = uuid.uuid4()

        mock_org = _make_mock_org(plan_tier="pro", org_id=org_id)
        mock_agent_result = MagicMock()
        mock_agent_result.scalar_one_or_none.return_value = MagicMock(id=agent_id)

        db_execute_calls = [0]

        async def counting_execute(stmt, *args, **kwargs):
            db_execute_calls[0] += 1
            if db_execute_calls[0] == 1:
                return mock_agent_result
            if db_execute_calls[0] == 2:
                return _make_stats_mock(_ZERO_STATS)
            return _make_stats_mock(_ZERO_NOVEL)

        async def override_get_db():
            db = AsyncMock()
            db.get = AsyncMock(return_value=mock_org)
            db.execute = counting_execute
            yield db

        app.dependency_overrides[get_db] = override_get_db
        try:
            r1 = await client.get(f"/api/v1/agents/{agent_id}/risk")
            assert r1.status_code == 200

            calls_after_first = db_execute_calls[0]  # should be 3 (agent + 2 SQL)

            r2 = await client.get(f"/api/v1/agents/{agent_id}/risk")
            assert r2.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert r1.json() == r2.json()
        # DB was not queried again on the second (cached) request
        assert db_execute_calls[0] == calls_after_first
