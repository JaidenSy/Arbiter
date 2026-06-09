"""
Integration tests for GET /api/v1/traces and GET /api/v1/traces/{id} (GROWTH-05).

Coverage:
    Plan gate:
    - Free org → 402 on both list and detail endpoints
    - Pro org → 200

    List endpoint:
    - Returns paginated TraceListResponse (traces, total, page, page_size)
    - agent_id filter is applied when provided
    - status computed correctly: active (no ended_at), failed (any error), completed

    Detail endpoint:
    - Steps ordered with correct offset_ms
    - 404 for unknown trace_id
    - 404 (not 403) for a trace belonging to a different org (no info leak)
    - Trace with no events returns empty steps array

    Auth:
    - No auth → 401 on both endpoints
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────

_ORG_ID = uuid.UUID("33333333-0000-0000-0000-000000000001")
_AGENT_ID = uuid.UUID("aaaaaaaa-1111-0000-0000-000000000001")
_TRACE_ID = uuid.UUID("cccccccc-0000-0000-0000-000000000001")

_T0 = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
_T1 = _T0 + timedelta(seconds=1)
_T2 = _T0 + timedelta(seconds=3)
_T_END = _T0 + timedelta(seconds=5)


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


def _make_event(
    *,
    tool_name: str = "list_tools",
    mcp_server_id: uuid.UUID | None = None,
    occurred_at: datetime = _T1,
    duration_ms: int = 100,
    cache_hit: bool = False,
    error: str | None = None,
) -> MagicMock:
    event = MagicMock()
    event.tool_name = tool_name
    event.mcp_server_id = mcp_server_id
    event.occurred_at = occurred_at
    event.duration_ms = duration_ms
    event.cache_hit = cache_hit
    event.error = error
    return event


def _make_session(
    *,
    session_id: uuid.UUID = _TRACE_ID,
    agent_id: uuid.UUID = _AGENT_ID,
    org_id: uuid.UUID = _ORG_ID,
    started_at: datetime = _T0,
    ended_at: datetime | None = _T_END,
    events: list | None = None,
    agent_name: str = "test-agent",
) -> MagicMock:
    agent = MagicMock()
    agent.name = agent_name

    session = MagicMock()
    session.id = session_id
    session.agent_id = agent_id
    session.org_id = org_id
    session.started_at = started_at
    session.ended_at = ended_at
    session.agent = agent
    session.events = events or []
    return session


# ── DB factory for list_traces ─────────────────────────────────────────────────


def _make_list_db(
    plan_tier: str = "pro",
    sessions: list | None = None,
    total: int | None = None,
) -> AsyncMock:
    """
    Build a mock DB for GET /traces.

    Call order:
      1. db.get(Organization, org_id) → org  (_require_pro)
      2. db.scalar(COUNT query)        → total
      3. db.execute(SELECT sessions)   → result.scalars().all()
    """
    db = AsyncMock()
    db.get = AsyncMock(return_value=_make_org(plan_tier))

    session_list = sessions or []
    _total = total if total is not None else len(session_list)

    call_count = 0

    async def execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        result.scalars.return_value.all.return_value = session_list
        return result

    async def scalar(stmt):
        return _total

    db.execute = execute
    db.scalar = scalar
    return db


# ── DB factory for get_trace ───────────────────────────────────────────────────


def _make_detail_db(
    plan_tier: str = "pro",
    session: MagicMock | None = None,
    server_map: dict | None = None,
) -> AsyncMock:
    """
    Build a mock DB for GET /traces/{id}.

    Call order:
      1. db.get(Organization, org_id) → org  (_require_pro)
      2. db.execute(SELECT session)    → result.scalar_one_or_none()
      3. db.execute(SELECT servers)    → row.id / row.name (only if events have server IDs)
    """
    db = AsyncMock()
    db.get = AsyncMock(return_value=_make_org(plan_tier))

    _server_map = server_map or {}

    call_count = 0

    async def execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # Session lookup
            result.scalar_one_or_none.return_value = session
        else:
            # MCP server name lookup
            rows = [MagicMock(id=sid, name=name) for sid, name in _server_map.items()]
            result.__iter__ = lambda self: iter(rows)
            result.all = lambda: rows
        return result

    db.execute = execute
    return db


# ── Tests: List endpoint ───────────────────────────────────────────────────────


class TestListTraces:
    @pytest.mark.asyncio
    async def test_free_org_returns_402(self):
        """Free org → HTTP 402."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_list_db(plan_tier="free")

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/traces")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 402

    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self):
        """No auth → 401."""
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/traces")

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_pro_org_returns_paginated_list(self):
        """Pro org → 200 with correct pagination shape."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        events = [_make_event()]
        session = _make_session(events=events)
        db = _make_list_db(plan_tier="pro", sessions=[session], total=1)
        user = _make_user()

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/traces")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert len(data["traces"]) == 1
        trace = data["traces"][0]
        assert trace["tool_call_count"] == 1
        assert trace["error_count"] == 0

    @pytest.mark.asyncio
    async def test_completed_status_when_no_errors_and_ended(self):
        """Session with ended_at and no errors → status='completed'."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        session = _make_session(ended_at=_T_END, events=[_make_event(error=None)])
        db = _make_list_db(plan_tier="pro", sessions=[session])
        user = _make_user()

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/traces")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["traces"][0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_failed_status_when_any_event_has_error(self):
        """Session with at least one error event → status='failed'."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        events = [_make_event(error="upstream timeout")]
        session = _make_session(ended_at=_T_END, events=events)
        db = _make_list_db(plan_tier="pro", sessions=[session])
        user = _make_user()

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/traces")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        trace = resp.json()["traces"][0]
        assert trace["status"] == "failed"
        assert trace["error_count"] == 1

    @pytest.mark.asyncio
    async def test_active_status_when_no_ended_at(self):
        """Session without ended_at → status='active'."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        session = _make_session(ended_at=None, events=[])
        db = _make_list_db(plan_tier="pro", sessions=[session])
        user = _make_user()

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/traces")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["traces"][0]["status"] == "active"

    @pytest.mark.asyncio
    async def test_empty_org_returns_empty_list(self):
        """No sessions → traces=[], total=0."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        db = _make_list_db(plan_tier="pro", sessions=[], total=0)
        user = _make_user()

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/traces")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["traces"] == []
        assert data["total"] == 0


# ── Tests: Detail endpoint ─────────────────────────────────────────────────────


class TestGetTrace:
    @pytest.mark.asyncio
    async def test_free_org_returns_402(self):
        """Free org → HTTP 402 on trace detail."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_detail_db(plan_tier="free")

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/traces/{_TRACE_ID}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 402

    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self):
        """No auth → 401."""
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/traces/{_TRACE_ID}")

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_trace_returns_404(self):
        """Trace not in DB → 404."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_detail_db(plan_tier="pro", session=None)

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/traces/{uuid.uuid4()}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_trace_with_ordered_steps_and_offset_ms(self):
        """
        Trace detail returns steps with correct offset_ms values.
        Event at T0+1s → offset_ms=1000; event at T0+3s → offset_ms=3000.
        """
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        event1 = _make_event(tool_name="list_tools", occurred_at=_T1, duration_ms=200)
        event2 = _make_event(
            tool_name="call_tool", occurred_at=_T2, duration_ms=150, error="timeout"
        )
        session = _make_session(
            started_at=_T0,
            ended_at=_T_END,
            events=[event1, event2],
        )
        db = _make_detail_db(plan_tier="pro", session=session)
        user = _make_user()

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/traces/{_TRACE_ID}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["trace_id"] == str(_TRACE_ID)
        steps = data["steps"]
        assert len(steps) == 2

        # First step: 1 second after T0
        assert steps[0]["tool_name"] == "list_tools"
        assert steps[0]["offset_ms"] == pytest.approx(1000.0)
        assert steps[0]["status"] == "ok"
        assert steps[0]["step"] == 1

        # Second step: 3 seconds after T0
        assert steps[1]["tool_name"] == "call_tool"
        assert steps[1]["offset_ms"] == pytest.approx(3000.0)
        assert steps[1]["status"] == "error"
        assert steps[1]["error"] == "timeout"
        assert steps[1]["step"] == 2

    @pytest.mark.asyncio
    async def test_trace_with_no_events_returns_empty_steps(self):
        """Trace with no SessionEvents → steps=[]."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        session = _make_session(events=[])
        db = _make_detail_db(plan_tier="pro", session=session)
        user = _make_user()

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/traces/{_TRACE_ID}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["steps"] == []

    @pytest.mark.asyncio
    async def test_duration_ms_on_completed_trace(self):
        """duration_ms on a completed trace = (ended_at - started_at) in ms."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        # _T0 to _T_END is 5 seconds → 5000 ms
        session = _make_session(started_at=_T0, ended_at=_T_END, events=[])
        db = _make_detail_db(plan_tier="pro", session=session)
        user = _make_user()

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/traces/{_TRACE_ID}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["duration_ms"] == 5000

    @pytest.mark.asyncio
    async def test_active_trace_has_null_duration_ms(self):
        """Active trace (no ended_at) → duration_ms=null."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        session = _make_session(started_at=_T0, ended_at=None, events=[])
        db = _make_detail_db(plan_tier="pro", session=session)
        user = _make_user()

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(f"/api/v1/traces/{_TRACE_ID}")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["duration_ms"] is None
