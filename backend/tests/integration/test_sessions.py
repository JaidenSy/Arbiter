"""
Integration tests for Session endpoints.

Coverage:
    GET /api/v1/sessions              — list ordered by started_at DESC
    GET /api/v1/sessions?agent_id=X  — filters by agent
    GET /api/v1/sessions/{id}         — includes events array
    GET /api/v1/sessions/{id}/events  — events ordered by occurred_at ASC

    404 cases:
    - GET /sessions/{non_existent} → 404
    - GET /sessions/{non_existent}/events → 404

    Empty state:
    - GET /sessions → [] when no sessions
    - GET /sessions/{id} → events: [] when session has no events
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_session_event(
    event_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    tool_name: str = "some_tool",
    cache_hit: bool = False,
    error: str | None = None,
) -> MagicMock:
    e = MagicMock()
    e.id = event_id or uuid.uuid4()
    e.session_id = session_id or uuid.uuid4()
    e.mcp_server_id = uuid.uuid4()
    # mcp_server_name is not an ORM column — explicitly set to None so that
    # Pydantic's from_attributes mode does not pick up a MagicMock sentinel.
    e.mcp_server_name = None
    e.tool_name = tool_name
    e.request_payload = {"input": "test"}
    e.response_payload = {"output": "ok"}
    e.cache_hit = cache_hit
    e.duration_ms = 42
    e.error = error
    e.occurred_at = datetime.now(tz=timezone.utc)
    return e


def _make_session(
    session_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    events: list | None = None,
) -> MagicMock:
    s = MagicMock()
    s.id = session_id or uuid.uuid4()
    s.agent_id = agent_id or uuid.uuid4()
    s.started_at = datetime.now(tz=timezone.utc)
    s.ended_at = None
    s.metadata_ = {}
    s.events = events if events is not None else []
    return s


def _make_db_list(sessions_list=None):
    """DB mock for GET /sessions."""
    db = AsyncMock()

    async def execute(stmt):
        result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = sessions_list or []
        result.scalars.return_value = scalars_mock
        return result

    db.execute = execute
    return db


def _make_db_get_session(session=None, events_list=None):
    """
    DB mock for GET /sessions/{id} and /sessions/{id}/events.
    First execute: session lookup.
    Second execute: events lookup.
    """
    db = AsyncMock()
    call_count = 0

    async def execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # Session lookup
            result.scalar_one_or_none.return_value = session
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = []
            result.scalars.return_value = scalars_mock
        else:
            # Events lookup (for /events endpoint)
            result.scalar_one_or_none.return_value = session
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = events_list or []
            result.scalars.return_value = scalars_mock
        return result

    db.execute = execute
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestListSessions:
    @pytest.mark.asyncio
    async def test_list_sessions_returns_200(self, authed_client):
        """GET /sessions → 200 with list of sessions."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        session = _make_session(agent_id=mock_agent.id)
        db = _make_db_list(sessions_list=[session])

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                "/api/v1/sessions",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_list_sessions_empty_when_no_sessions(self, authed_client):
        """GET /sessions → [] when no sessions exist."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_db_list(sessions_list=[])

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                "/api/v1/sessions",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_agent_id(self, authed_client):
        """GET /sessions?agent_id={id} passes filter to query."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        target_agent_id = uuid.uuid4()
        session = _make_session(agent_id=target_agent_id)
        db = _make_db_list(sessions_list=[session])

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/sessions?agent_id={target_agent_id}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert len(items) == 1
        assert items[0]["agent_id"] == str(target_agent_id)

    @pytest.mark.asyncio
    async def test_list_sessions_requires_auth(self, test_client):
        """GET /sessions without auth → 401."""
        resp = await test_client.get("/api/v1/sessions")
        assert resp.status_code == 401


class TestGetSession:
    @pytest.mark.asyncio
    async def test_get_session_includes_events(self, authed_client):
        """GET /sessions/{id} → 200 with events array."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        session_id = uuid.uuid4()
        event = _make_session_event(session_id=session_id)
        session = _make_session(session_id=session_id, events=[event])
        db = _make_db_get_session(session=session)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/sessions/{session_id}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["id"] == str(session_id)
        assert "events" in data
        assert len(data["events"]) == 1

    @pytest.mark.asyncio
    async def test_get_session_events_empty_list(self, authed_client):
        """GET /sessions/{id} → events: [] when session has no events."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        session_id = uuid.uuid4()
        session = _make_session(session_id=session_id, events=[])
        db = _make_db_get_session(session=session)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/sessions/{session_id}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        assert resp.json()["events"] == []

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_returns_404(self, authed_client):
        """GET /sessions/{non_existent_id} → 404."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_db_get_session(session=None)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/sessions/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404, resp.text


class TestListSessionEvents:
    @pytest.mark.asyncio
    async def test_list_events_returns_200(self, authed_client):
        """GET /sessions/{id}/events → 200 with events list."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        session_id = uuid.uuid4()
        session = _make_session(session_id=session_id)
        event1 = _make_session_event(session_id=session_id, tool_name="tool_a")
        event2 = _make_session_event(session_id=session_id, tool_name="tool_b")
        db = _make_db_get_session(session=session, events_list=[event1, event2])

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/sessions/{session_id}/events",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200, resp.text
        events = resp.json()
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_list_events_nonexistent_session_returns_404(self, authed_client):
        """GET /sessions/{non_existent_id}/events → 404."""
        client, raw_key, mock_agent = authed_client

        from app.main import app
        from app.core.dependencies import get_db

        db = _make_db_get_session(session=None)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db

        try:
            resp = await client.get(
                f"/api/v1/sessions/{uuid.uuid4()}/events",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 404, resp.text
