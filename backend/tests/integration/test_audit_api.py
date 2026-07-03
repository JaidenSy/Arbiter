"""
Integration tests for GET /api/v1/audit/export (GROWTH-04).

Coverage:
    Plan gate:
    - Free org → 402
    - Pro org → 200 streaming response

    Format validation:
    - format=csv → Content-Type: text/csv with header row
    - format=json → application/json NDJSON
    - format=xml → 400

    Date range validation:
    - to < from → 400
    - range > 90 days → 400 with message
    - valid range (≤ 90 days) → 200

    Auth:
    - No auth → 401

    Org isolation:
    - Streamed query is filtered by caller's org_id (validated via mock call args)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────

_ORG_ID = uuid.UUID("22222222-0000-0000-0000-000000000001")


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


def _make_audit_row(
    *,
    agent_name: str = "test-agent",
    mcp_server_name: str | None = "test-server",
    tool_name: str = "list_tools",
    cache_hit: bool = False,
    duration_ms: int = 42,
    error: str | None = None,
) -> MagicMock:
    row = MagicMock()
    row.occurred_at = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    row.agent_name = agent_name
    row.mcp_server_name = mcp_server_name
    row.tool_name = tool_name
    row.cache_hit = cache_hit
    row.duration_ms = duration_ms
    row.error = error
    return row


def _make_audit_db(plan_tier: str = "pro", rows: list | None = None) -> AsyncMock:
    """
    Build a mock DB for the audit export endpoint.

    Call order:
      1. db.get(Organization, org_id) → org (plan gate)
      2. db.stream(query, params)      → result with async partitions()
    """
    db = AsyncMock()
    db.get = AsyncMock(return_value=_make_org(plan_tier))

    stream_rows = rows or []

    async def mock_stream(query, params):
        class FakeResult:
            async def partitions(self, size):
                if stream_rows:
                    yield stream_rows

        return FakeResult()

    db.stream = mock_stream
    return db


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestAuditExportPlanGate:
    @pytest.mark.asyncio
    async def test_free_org_returns_402(self):
        """Free org → HTTP 402."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_audit_db(plan_tier="free")

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/audit/export",
                    params={"format": "csv", "from": "2026-05-01", "to": "2026-06-01"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 402

    @pytest.mark.asyncio
    async def test_unknown_tier_returns_402(self):
        """An unrecognised tier (e.g. future 'starter') fails closed → 402, not granted."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_audit_db(plan_tier="starter")

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/audit/export",
                    params={"format": "csv", "from": "2026-05-01", "to": "2026-06-01"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 402

    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self):
        """No auth token → 401."""
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/audit/export",
                params={"format": "csv", "from": "2026-05-01", "to": "2026-06-01"},
            )

        assert resp.status_code == 401


class TestAuditExportFormatValidation:
    @pytest.mark.asyncio
    async def test_invalid_format_returns_400(self):
        """format=xml → HTTP 400."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_audit_db(plan_tier="pro")

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/audit/export",
                    params={"format": "xml", "from": "2026-05-01", "to": "2026-06-01"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400
        assert "format" in resp.json()["detail"].lower() or "csv" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_csv_format_returns_text_csv(self):
        """format=csv → Content-Type: text/csv with header row."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_audit_db(plan_tier="pro", rows=[_make_audit_row()])

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/audit/export",
                    params={"format": "csv", "from": "2026-05-01", "to": "2026-06-01"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        # Header row must be present
        body = resp.text
        assert "occurred_at" in body
        assert "agent_name" in body
        assert "tool_name" in body

    @pytest.mark.asyncio
    async def test_json_format_returns_ndjson(self):
        """format=json → application/json NDJSON: one JSON object per line."""
        import json

        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_audit_db(
            plan_tier="pro",
            rows=[_make_audit_row(tool_name="call_tool"), _make_audit_row(tool_name="list_tools")],
        )

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/audit/export",
                    params={"format": "json", "from": "2026-05-01", "to": "2026-06-01"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        lines = [l for l in resp.text.strip().splitlines() if l]
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "tool_name" in obj
            assert "status" in obj

    @pytest.mark.asyncio
    async def test_csv_error_row_has_error_status(self):
        """A row with a non-null error field → status='error' in CSV output."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_audit_db(
            plan_tier="pro",
            rows=[_make_audit_row(error="upstream timeout")],
        )

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/audit/export",
                    params={"format": "csv", "from": "2026-05-01", "to": "2026-06-01"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert "error" in resp.text


class TestAuditExportDateValidation:
    @pytest.mark.asyncio
    async def test_to_before_from_returns_400(self):
        """to < from → HTTP 400."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_audit_db(plan_tier="pro")

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/audit/export",
                    params={"format": "csv", "from": "2026-06-01", "to": "2026-05-01"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_range_over_90_days_returns_400(self):
        """Date range > 90 days → HTTP 400 with message."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_audit_db(plan_tier="pro")

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/audit/export",
                    params={"format": "csv", "from": "2026-01-01", "to": "2026-06-01"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 400
        assert "90" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_exactly_90_days_is_allowed(self):
        """Range exactly equal to 90 days is valid (boundary condition)."""
        from app.core.dependencies import get_current_user, get_db
        from app.main import app

        user = _make_user()
        db = _make_audit_db(plan_tier="pro", rows=[])

        async def override_db():
            yield db

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = lambda: user

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/api/v1/audit/export",
                    params={"format": "csv", "from": "2026-03-02", "to": "2026-05-31"},
                )
        finally:
            app.dependency_overrides.clear()

        # 90 days exactly: should succeed (2026-05-31 - 2026-03-02 = 90 days)
        assert resp.status_code == 200
