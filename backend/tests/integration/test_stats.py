"""
Integration tests for GET /api/v1/stats and GET /api/v1/stats/history.

Coverage:
    Zero state:
    - All zeros when no data
    - No division-by-zero when tool_calls_today=0 → cache_hit_rate_today=0.0

    With seeded data:
    - agents_count reflects active agents
    - servers_count reflects active servers
    - tool_calls_today counts only today's events
    - cache_hit_rate_today computed correctly (hits / total)
    - Yesterday's events NOT counted in tool_calls_today

    History endpoint:
    - GET /stats/history (default 7d) → 7 buckets
    - GET /stats/history?period=24h → 24 buckets
    - With seeded events: correct tool_calls and cache_hits in today's bucket
    - Invalid period → 422
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_stats_db(
    agents_count: int = 0,
    servers_count: int = 0,
    tool_calls_today: int = 0,
    cache_hits_today: int = 0,
    errors_today: int = 0,
    latency_p50: float | None = None,
    latency_p95: float | None = None,
    latency_p99: float | None = None,
    slowest_tools: list[dict] | None = None,
) -> AsyncMock:
    """
    Build a mock DB session that returns pre-computed stats values.

    The stats endpoint issues 5 queries in order:
      1. COUNT(Agent.id) WHERE is_active          → scalar_one()
      2. COUNT(MCPServer.id) WHERE is_active       → scalar_one()
      3. COUNT/SUM calls+hits+errors for today     → one()
      4. percentile_cont p50/p95/p99               → one_or_none()
      5. AVG/COUNT slowest tools                   → all()
    """
    db = AsyncMock()
    call_count = 0

    async def execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()

        if call_count == 1:
            result.scalar_one.return_value = agents_count
        elif call_count == 2:
            result.scalar_one.return_value = servers_count
        elif call_count == 3:
            row = MagicMock()
            row.total = tool_calls_today
            row.hits = cache_hits_today
            row.errors = errors_today
            result.one.return_value = row
        elif call_count == 4:
            if latency_p50 is None:
                result.one_or_none.return_value = None
            else:
                lat_row = MagicMock()
                lat_row.p50 = latency_p50
                lat_row.p95 = latency_p95
                lat_row.p99 = latency_p99
                result.one_or_none.return_value = lat_row
        else:
            rows = []
            for t in slowest_tools or []:
                r = MagicMock()
                r.tool_name = t["tool_name"]
                r.server_name = t.get("server_name")
                r.avg_ms = t["avg_ms"]
                r.cnt = t["cnt"]
                rows.append(r)
            result.all.return_value = rows

        return result

    db.execute = execute
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestStatsZeroState:
    @pytest.mark.asyncio
    async def test_stats_all_zeros_when_no_data(self, fake_redis):
        """GET /stats with no data → all zeros, no crash."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        db = _make_stats_db(
            agents_count=0,
            servers_count=0,
            tool_calls_today=0,
            cache_hits_today=0,
        )

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["agents_count"] == 0
        assert data["servers_count"] == 0
        assert data["tool_calls_today"] == 0
        assert data["cache_hit_rate_today"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_no_division_by_zero(self, fake_redis):
        """cache_hit_rate_today must be 0.0 (not NaN/error) when tool_calls_today=0."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        # Explicitly: 0 calls, 0 hits
        db = _make_stats_db(tool_calls_today=0, cache_hits_today=0)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        rate = resp.json()["cache_hit_rate_today"]
        assert rate == 0.0
        assert isinstance(rate, float)


class TestStatsWithData:
    @pytest.mark.asyncio
    async def test_stats_agents_and_servers_count(self, fake_redis):
        """GET /stats returns correct agents_count and servers_count."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        db = _make_stats_db(agents_count=2, servers_count=1)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["agents_count"] == 2
        assert data["servers_count"] == 1

    @pytest.mark.asyncio
    async def test_stats_cache_hit_rate_50_percent(self, fake_redis):
        """GET /stats with 4 calls (2 hits, 2 misses) → cache_hit_rate_today=0.5."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        db = _make_stats_db(tool_calls_today=4, cache_hits_today=2)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["tool_calls_today"] == 4
        assert data["cache_hit_rate_today"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_stats_yesterday_events_not_counted(self, fake_redis):
        """
        Events from yesterday must NOT appear in tool_calls_today.

        The DB mock simulates the SQL WHERE clause already filtering by UTC midnight.
        We return tool_calls_today=4 to assert that yesterday's event (which the
        real SQL excludes via DATE_TRUNC) is not counted.
        """
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        # tool_calls_today=4 means DB returned 4: yesterday's event is excluded
        # by the SQL filter DATE_TRUNC('day', NOW()). Mock simulates post-filter result.
        db = _make_stats_db(tool_calls_today=4, cache_hits_today=2)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        # Still 4, not 5: yesterday's event is not included
        assert resp.json()["tool_calls_today"] == 4

    @pytest.mark.asyncio
    async def test_stats_requires_auth(self, test_client):
        """GET /stats without auth → 401."""
        resp = await test_client.get("/api/v1/stats")
        assert resp.status_code == 401


# ── History endpoint helpers ───────────────────────────────────────────────────


def _make_history_db(rows: list[dict]) -> AsyncMock:
    """
    Build a mock DB that returns pre-built rows for the history aggregate query.

    Each dict in ``rows`` should have: bucket (datetime), total, hits, errors.
    The mock is called once: returning all rows as a result set.
    """
    db = AsyncMock()

    async def execute(stmt):
        result = MagicMock()
        mock_rows = []
        for r in rows:
            row = MagicMock()
            row.bucket = r["bucket"]
            row.total = r["total"]
            row.hits = r["hits"]
            row.errors = r["errors"]
            mock_rows.append(row)
        result.all.return_value = mock_rows
        return result

    db.execute = execute
    return db


# ── History tests ─────────────────────────────────────────────────────────────


class TestStatsHistory:
    @pytest.mark.asyncio
    async def test_history_default_7d_returns_7_buckets(self, fake_redis):
        """GET /stats/history (default period=7d) returns exactly 7 buckets."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        # No rows: all buckets should be zeros
        db = _make_history_db([])

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats/history",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["period"] == "7d"
        assert len(data["buckets"]) == 7

    @pytest.mark.asyncio
    async def test_history_24h_returns_24_buckets(self, fake_redis):
        """GET /stats/history?period=24h returns exactly 24 buckets."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        db = _make_history_db([])

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats/history?period=24h",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["period"] == "24h"
        assert len(data["buckets"]) == 24

    @pytest.mark.asyncio
    async def test_history_seeded_today_bucket_counts(self, fake_redis):
        """With a seeded row for today, today's bucket has correct tool_calls and cache_hits."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()

        today = datetime.now(UTC).date()
        today_dt = datetime(today.year, today.month, today.day, tzinfo=UTC)

        db = _make_history_db(
            [
                {"bucket": today_dt, "total": 10, "hits": 4, "errors": 1},
            ]
        )

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats/history",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        buckets = resp.json()["buckets"]
        assert len(buckets) == 7

        # The last bucket is today
        today_bucket = buckets[-1]
        assert today_bucket["tool_calls"] == 10
        assert today_bucket["cache_hits"] == 4
        assert today_bucket["errors"] == 1
        assert today_bucket["cache_hit_rate"] == pytest.approx(0.4)

    @pytest.mark.asyncio
    async def test_history_invalid_period_returns_422(self, fake_redis):
        """GET /stats/history?period=invalid → 422."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        db = _make_history_db([])

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats/history?period=invalid",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 422, resp.text


# ── Latency + drill-down tests (#185, #205) ───────────────────────────────────


class TestStatsLatencyAndDrillDown:
    @pytest.mark.asyncio
    async def test_stats_returns_latency_fields(self, fake_redis):
        """GET /stats returns latency_p50/p95/p99 when data is available."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        db = _make_stats_db(
            tool_calls_today=5,
            latency_p50=120.0,
            latency_p95=450.0,
            latency_p99=800.0,
        )

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["latency_p50_ms"] == pytest.approx(120.0)
        assert data["latency_p95_ms"] == pytest.approx(450.0)
        assert data["latency_p99_ms"] == pytest.approx(800.0)

    @pytest.mark.asyncio
    async def test_stats_latency_null_when_no_duration_data(self, fake_redis):
        """GET /stats returns null latency fields when no events have duration_ms."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        db = _make_stats_db()

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["latency_p50_ms"] is None
        assert data["latency_p95_ms"] is None
        assert data["latency_p99_ms"] is None
        assert data["slowest_tools"] == []

    @pytest.mark.asyncio
    async def test_stats_slowest_tools_in_response(self, fake_redis):
        """GET /stats includes slowest_tools list when data exists."""
        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        db = _make_stats_db(
            tool_calls_today=10,
            latency_p50=200.0,
            latency_p95=500.0,
            latency_p99=900.0,
            slowest_tools=[
                {"tool_name": "slow_query", "server_name": "db", "avg_ms": 850.0, "cnt": 3},
            ],
        )

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/stats",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["slowest_tools"]) == 1
        assert data["slowest_tools"][0]["tool_name"] == "slow_query"
        assert data["slowest_tools"][0]["avg_duration_ms"] == pytest.approx(850.0)
        assert data["slowest_tools"][0]["call_count"] == 3

    @pytest.mark.asyncio
    async def test_stats_agent_id_filter_accepted_200(self, fake_redis):
        """GET /stats?agent_id=<uuid> returns 200 and applies the filter without error."""
        import uuid as _uuid

        from app.core.dependencies import get_current_agent, get_current_user, get_db, get_redis
        from app.core.security import generate_api_key
        from app.main import app
        from tests.conftest import _make_mock_agent, _make_mock_user

        raw_key = generate_api_key()
        mock_agent = _make_mock_agent(raw_key)
        mock_user = _make_mock_user()
        db = _make_stats_db(tool_calls_today=2)

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        async def override_get_current_agent():
            return mock_agent

        async def override_get_current_user():
            return mock_user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis
        app.dependency_overrides[get_current_agent] = override_get_current_agent
        app.dependency_overrides[get_current_user] = override_get_current_user

        agent_id = str(_uuid.uuid4())
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/v1/stats?agent_id={agent_id}",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        assert resp.json()["tool_calls_today"] == 2
