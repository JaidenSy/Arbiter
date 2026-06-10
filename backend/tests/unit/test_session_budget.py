"""
Unit tests for per-session tool-call budget enforcement (#211).

Coverage:
    SessionBudgetExceededError:
        - Attributes stored correctly
        - str representation includes used/limit/session_id
    proxy_service budget enforcement:
        - Increments counter on each call
        - Raises SessionBudgetExceededError when used > max_calls_per_session
        - Does NOT raise when used == max_calls_per_session (exactly at limit is allowed)
        - Skips budget check when max_calls_per_session is None
        - Sets 24h TTL on first increment
"""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.plan.plan_limits import SessionBudgetExceededError
from app.services.proxy.proxy_service import ProxyService

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_ok_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {}
    resp.json.return_value = {"result": {"content": "ok"}}
    resp.text = '{"result": {"content": "ok"}}'
    return resp


def _make_service(redis: AsyncMock | None = None) -> tuple[ProxyService, AsyncMock]:
    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(plan_tier="free", id=uuid.uuid4()))
    r = redis or AsyncMock()
    return ProxyService(db, r), r


def _make_agent(max_calls: int | None = None) -> MagicMock:
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.org_id = uuid.uuid4()
    agent.name = "test-agent"
    agent.scope = "full"
    agent.rate_limit_per_minute = None
    agent.max_calls_per_session = max_calls
    return agent


def _make_server(org_id: uuid.UUID) -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.org_id = org_id
    s.name = "test-server"
    s.base_url = "http://fake-mcp:9000"
    s.headers = {}
    s.cache_enabled = False
    return s


def _make_session(agent_id: uuid.UUID, org_id: uuid.UUID) -> MagicMock:
    sess = MagicMock()
    sess.id = uuid.uuid4()
    sess.agent_id = agent_id
    sess.org_id = org_id
    return sess


def _make_event() -> MagicMock:
    evt = MagicMock()
    evt.id = uuid.uuid4()
    return evt


def _make_request():
    from app.schemas.proxy import ToolCallRequest

    return ToolCallRequest(server_name="test-server", tool_name="read_file", params={})


def _apply_deps(
    stack: ExitStack, service: ProxyService, server: MagicMock, session: MagicMock, event: MagicMock
) -> None:
    stack.enter_context(patch.object(service, "resolve_server", new=AsyncMock(return_value=server)))
    stack.enter_context(
        patch.object(service._rbac, "check_permission", new=AsyncMock(return_value=True))
    )
    stack.enter_context(
        patch.object(service._rbac, "get_rate_limit", new=AsyncMock(return_value=None))
    )
    stack.enter_context(
        patch("app.services.proxy.proxy_service.check_tool_call_quota", new=AsyncMock())
    )
    stack.enter_context(patch.object(service, "intercept_request", new=AsyncMock(return_value={})))
    stack.enter_context(
        patch.object(service, "_ensure_mcp_session", new=AsyncMock(return_value={}))
    )
    stack.enter_context(
        patch.object(service, "_ensure_session", new=AsyncMock(return_value=session))
    )
    stack.enter_context(patch.object(service, "_persist_event", new=AsyncMock(return_value=event)))
    stack.enter_context(patch("app.services.proxy.proxy_service.assert_ssrf_safe", new=AsyncMock()))
    stack.enter_context(
        patch("app.services.proxy.proxy_service.PLAN_LIMITS", {"free": {"semantic_cache": False}})
    )


# ── SessionBudgetExceededError unit tests ─────────────────────────────────────


class TestSessionBudgetExceededError:
    def test_attributes_stored(self):
        sid = str(uuid.uuid4())
        err = SessionBudgetExceededError(session_id=sid, used=4, limit=3)
        assert err.session_id == sid
        assert err.used == 4
        assert err.limit == 3

    def test_str_includes_context(self):
        sid = str(uuid.uuid4())
        err = SessionBudgetExceededError(session_id=sid, used=4, limit=3)
        msg = str(err)
        assert "4" in msg
        assert "3" in msg
        assert sid in msg

    def test_is_exception(self):
        err = SessionBudgetExceededError(session_id="x", used=1, limit=1)
        assert isinstance(err, Exception)


# ── Proxy budget enforcement tests ───────────────────────────────────────────


class TestSessionBudgetEnforcement:
    @pytest.mark.asyncio
    async def test_raises_when_over_budget(self):
        """4th call with limit=3 must raise SessionBudgetExceededError."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.incr = AsyncMock(return_value=4)  # 4th call
        redis.expire = AsyncMock()

        service, _ = _make_service(redis)
        agent = _make_agent(max_calls=3)
        server = _make_server(agent.org_id)
        session = _make_session(agent.id, agent.org_id)
        event = _make_event()

        class MockClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                return _make_ok_response()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.services.proxy.proxy_service.httpx.AsyncClient", return_value=MockClient()
                )
            )
            _apply_deps(stack, service, server, session, event)
            with pytest.raises(SessionBudgetExceededError) as exc_info:
                await service.forward_tool_call(_make_request(), agent)

        err = exc_info.value
        assert err.used == 4
        assert err.limit == 3

    @pytest.mark.asyncio
    async def test_passes_at_exact_limit(self):
        """3rd call with limit=3 must succeed (used == limit is still OK)."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.incr = AsyncMock(return_value=3)  # exactly at limit
        redis.expire = AsyncMock()

        service, _ = _make_service(redis)
        agent = _make_agent(max_calls=3)
        server = _make_server(agent.org_id)
        session = _make_session(agent.id, agent.org_id)
        event = _make_event()

        class MockClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                return _make_ok_response()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.services.proxy.proxy_service.httpx.AsyncClient", return_value=MockClient()
                )
            )
            _apply_deps(stack, service, server, session, event)
            resp = await service.forward_tool_call(_make_request(), agent)

        assert resp is not None

    @pytest.mark.asyncio
    async def test_skips_budget_check_when_none(self):
        """Agent with max_calls_per_session=None must never raise SessionBudgetExceededError."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.incr = AsyncMock(return_value=9999)  # high count, shouldn't matter
        redis.expire = AsyncMock()

        service, _ = _make_service(redis)
        agent = _make_agent(max_calls=None)
        server = _make_server(agent.org_id)
        session = _make_session(agent.id, agent.org_id)
        event = _make_event()

        class MockClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                return _make_ok_response()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.services.proxy.proxy_service.httpx.AsyncClient", return_value=MockClient()
                )
            )
            _apply_deps(stack, service, server, session, event)
            resp = await service.forward_tool_call(_make_request(), agent)

        assert resp is not None
        redis.incr.assert_not_called()

    @pytest.mark.asyncio
    async def test_ttl_set_on_first_increment(self):
        """Redis expire must be called when incr returns 1 (first call in session)."""
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock()

        service, _ = _make_service(redis)
        agent = _make_agent(max_calls=10)
        server = _make_server(agent.org_id)
        session = _make_session(agent.id, agent.org_id)
        event = _make_event()

        class MockClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                return _make_ok_response()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.services.proxy.proxy_service.httpx.AsyncClient", return_value=MockClient()
                )
            )
            _apply_deps(stack, service, server, session, event)
            await service.forward_tool_call(_make_request(), agent)

        redis.expire.assert_called_once()
        args = redis.expire.call_args[0]
        assert f"session_budget:{session.id}" == args[0]
        assert args[1] == 86_400
