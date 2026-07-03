"""
Unit tests verifying RISK-2 and RISK-4 fixes.

RISK-2 (usage quota persistence):
    _persist_event() must execute a UsageEvent upsert (INSERT … ON CONFLICT)
    so that daily tool_calls and cache_hits counters actually increment.

RISK-4 (JWT TTL):
    jwt_access_token_expire_minutes must be ≤ 60.
    create_access_token() must embed an exp claim no more than 61 minutes
    in the future (1 min tolerance for test execution time).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# RISK-4: JWT TTL ≤ 60 minutes
# ─────────────────────────────────────────────────────────────────────────────

class TestJwtTtl:
    def test_config_ttl_is_at_most_60_minutes(self):
        """
        jwt_access_token_expire_minutes must be ≤ 60.
        Previously this was 1440 (24 h): the RISK-4 fix reduced it.
        """
        from app.core.config import settings

        assert settings.jwt_access_token_expire_minutes <= 60, (
            f"RISK-4: JWT TTL is {settings.jwt_access_token_expire_minutes} min: "
            "must be ≤ 60 (was 1440 before fix)"
        )

    def test_access_token_exp_within_61_minutes(self):
        """
        Tokens issued by create_access_token() must expire within 61 minutes
        of now (extra minute for test execution tolerance).
        """
        import jwt as pyjwt
        from app.core.config import settings
        from app.core.security import create_access_token

        before = datetime.now(tz=timezone.utc)
        token = create_access_token(
            user_id=uuid.uuid4(),
            org_id=uuid.uuid4(),
            role="member",
        )
        payload = pyjwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        delta = exp - before

        assert delta <= timedelta(minutes=61), (
            f"RISK-4: token exp is {delta.total_seconds() / 60:.1f} min from now: "
            "must be ≤ 61 min"
        )
        assert delta > timedelta(minutes=0), "Token is already expired"

    def test_access_token_type_claim(self):
        """Token type claim must be 'access' so decode_access_token() accepts it."""
        import jwt as pyjwt
        from app.core.config import settings
        from app.core.security import create_access_token

        token = create_access_token(
            user_id=uuid.uuid4(),
            org_id=uuid.uuid4(),
            role="admin",
        )
        payload = pyjwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        assert payload.get("type") == "access"


# ─────────────────────────────────────────────────────────────────────────────
# RISK-2: _persist_event() writes to usage_events
# ─────────────────────────────────────────────────────────────────────────────

def _make_session(org_id: uuid.UUID | None = None) -> MagicMock:
    session = MagicMock()
    session.id = uuid.uuid4()
    session.org_id = org_id or uuid.uuid4()
    return session


def _make_mcp_server() -> MagicMock:
    server = MagicMock()
    server.id = uuid.uuid4()
    server.name = "test-server"
    return server


def _make_proxy_service_mocks():
    """Return (db, redis) mocks suitable for ProxyService unit tests."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    redis = AsyncMock()
    return db, redis


class TestPersistEventUsageUpsert:
    """
    Verify that _persist_event() fires a UsageEvent upsert.

    We patch both pg_insert (to capture the statement) and SessionEvent
    (to avoid SQLAlchemy mapper initialization in a unit-test context).
    """

    @pytest.mark.asyncio
    async def test_persist_event_executes_usage_upsert_on_tool_call(self):
        """
        After writing a SessionEvent, _persist_event() must execute a
        pg_insert(UsageEvent) statement: the RISK-2 fix.
        """
        db, redis = _make_proxy_service_mocks()

        with patch("app.services.proxy.proxy_service.SessionEvent") as mock_se, \
             patch("app.services.proxy.proxy_service.pg_insert") as mock_pg_insert:
            mock_se.return_value = MagicMock()
            mock_stmt = MagicMock()
            mock_pg_insert.return_value.values.return_value.on_conflict_do_update.return_value = (
                mock_stmt
            )

            from app.services.proxy.proxy_service import ProxyService
            from app.db.models.usage_event import UsageEvent

            svc = ProxyService(db=db, redis=redis)
            session = _make_session()
            mcp_server = _make_mcp_server()

            await svc._persist_event(
                session=session,
                mcp_server=mcp_server,
                tool_name="read_file",
                request_payload={"path": "/tmp/x"},
                response_payload={"content": "ok"},
                cache_hit=False,
                duration_ms=42,
                error=None,
            )

        # pg_insert must have been called with the UsageEvent model.
        mock_pg_insert.assert_called_once_with(UsageEvent)

        # .values() must include org_id and tool_calls.
        values_kwargs = mock_pg_insert.return_value.values.call_args.kwargs
        assert "org_id" in values_kwargs, "UsageEvent upsert missing org_id"
        assert values_kwargs.get("tool_calls") == 1, (
            f"Expected tool_calls=1 in upsert values, got {values_kwargs.get('tool_calls')}"
        )

        # db.execute must have been called (the upsert statement was sent).
        db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_persist_event_increments_cache_hits_on_cache_hit(self):
        """cache_hit=True must set cache_hits=1 in the insert values."""
        db, redis = _make_proxy_service_mocks()

        with patch("app.services.proxy.proxy_service.SessionEvent") as mock_se, \
             patch("app.services.proxy.proxy_service.pg_insert") as mock_pg_insert:
            mock_se.return_value = MagicMock()
            mock_stmt = MagicMock()
            mock_pg_insert.return_value.values.return_value.on_conflict_do_update.return_value = (
                mock_stmt
            )

            from app.services.proxy.proxy_service import ProxyService

            svc = ProxyService(db=db, redis=redis)
            session = _make_session()
            mcp_server = _make_mcp_server()

            await svc._persist_event(
                session=session,
                mcp_server=mcp_server,
                tool_name="list_dir",
                request_payload={},
                response_payload={"items": []},
                cache_hit=True,
                duration_ms=5,
                error=None,
            )

        values_kwargs = mock_pg_insert.return_value.values.call_args.kwargs
        assert values_kwargs.get("cache_hits") == 1, (
            f"Expected cache_hits=1 for a cache hit, got {values_kwargs.get('cache_hits')}"
        )

    @pytest.mark.asyncio
    async def test_persist_event_zero_cache_hits_on_cache_miss(self):
        """cache_hit=False must set cache_hits=0 in the insert values."""
        db, redis = _make_proxy_service_mocks()

        with patch("app.services.proxy.proxy_service.SessionEvent") as mock_se, \
             patch("app.services.proxy.proxy_service.pg_insert") as mock_pg_insert:
            mock_se.return_value = MagicMock()
            mock_stmt = MagicMock()
            mock_pg_insert.return_value.values.return_value.on_conflict_do_update.return_value = (
                mock_stmt
            )

            from app.services.proxy.proxy_service import ProxyService

            svc = ProxyService(db=db, redis=redis)
            session = _make_session()
            mcp_server = _make_mcp_server()

            await svc._persist_event(
                session=session,
                mcp_server=mcp_server,
                tool_name="write_file",
                request_payload={"path": "/tmp/y", "content": "data"},
                response_payload=None,
                cache_hit=False,
                duration_ms=200,
                error=None,
            )

        values_kwargs = mock_pg_insert.return_value.values.call_args.kwargs
        assert values_kwargs.get("cache_hits") == 0, (
            f"Expected cache_hits=0 for a cache miss, got {values_kwargs.get('cache_hits')}"
        )

    @pytest.mark.asyncio
    async def test_persist_event_upsert_uses_org_date_conflict_constraint(self):
        """
        The ON CONFLICT clause must target the uq_usage_events_org_date constraint
        so rows are upserted, not duplicated.
        """
        db, redis = _make_proxy_service_mocks()

        with patch("app.services.proxy.proxy_service.SessionEvent") as mock_se, \
             patch("app.services.proxy.proxy_service.pg_insert") as mock_pg_insert:
            mock_se.return_value = MagicMock()
            mock_values = MagicMock()
            mock_pg_insert.return_value.values.return_value = mock_values
            mock_values.on_conflict_do_update.return_value = MagicMock()

            from app.services.proxy.proxy_service import ProxyService

            svc = ProxyService(db=db, redis=redis)
            session = _make_session()
            mcp_server = _make_mcp_server()

            await svc._persist_event(
                session=session,
                mcp_server=mcp_server,
                tool_name="test_tool",
                request_payload={},
                response_payload={},
                cache_hit=False,
                duration_ms=1,
                error=None,
            )

        conflict_kwargs = mock_values.on_conflict_do_update.call_args.kwargs
        assert conflict_kwargs.get("constraint") == "uq_usage_events_org_date", (
            f"Expected conflict constraint 'uq_usage_events_org_date', "
            f"got {conflict_kwargs.get('constraint')!r}"
        )
