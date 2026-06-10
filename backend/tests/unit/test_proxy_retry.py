"""
Unit tests for ProxyService HTTP retry logic (#181).

Verifies:
    - Retries up to _MAX_RETRIES times on TimeoutException
    - Retries on ConnectError as well
    - Exponential backoff (1s then 2s) between retries
    - Stops retrying after _MAX_RETRIES exhausted and raises 502
"""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from app.services.proxy.proxy_service import _MAX_RETRIES, ProxyService

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_ok_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {}
    resp.json.return_value = {"result": {"content": "ok"}}
    resp.text = '{"result": {"content": "ok"}}'
    return resp


def _make_service() -> ProxyService:
    db = AsyncMock()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(plan_tier="free", id=uuid.uuid4()))
    return ProxyService(db, redis)


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


def _make_agent() -> MagicMock:
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.org_id = uuid.uuid4()
    agent.name = "test-agent"
    agent.scope = "full"
    agent.rate_limit_per_minute = None
    agent.max_calls_per_session = None
    return agent


def _make_request():
    from app.schemas.proxy import ToolCallRequest

    return ToolCallRequest(server_name="test-server", tool_name="read_file", params={})


def _apply_deps(
    stack: ExitStack,
    service: ProxyService,
    server: MagicMock,
    session: MagicMock,
    event: MagicMock,
    sleep_mock: AsyncMock | None = None,
) -> None:
    """Enter all dependency patches onto the provided ExitStack."""
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
    stack.enter_context(
        patch("app.services.proxy.proxy_service.asyncio.sleep", new=sleep_mock or AsyncMock())
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestProxyRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_second_attempt_after_timeout(self):
        """When first attempt times out, second attempt succeeds."""
        service = _make_service()
        agent = _make_agent()
        server = _make_server(agent.org_id)
        session = _make_session(agent.id, agent.org_id)
        event = _make_event()
        request = _make_request()

        call_count = 0

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise httpx.TimeoutException("timeout")
                return _make_ok_response()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.services.proxy.proxy_service.httpx.AsyncClient",
                    return_value=MockAsyncClient(),
                )
            )
            _apply_deps(stack, service, server, session, event)
            resp = await service.forward_tool_call(request, agent)

        assert resp.tool_name == "read_file"
        assert call_count == 2  # failed once, succeeded on retry

    @pytest.mark.asyncio
    async def test_backoff_sleep_called_between_retries(self):
        """asyncio.sleep is called with 1s then 2s between retries."""
        service = _make_service()
        agent = _make_agent()
        server = _make_server(agent.org_id)
        session = _make_session(agent.id, agent.org_id)
        event = _make_event()
        request = _make_request()

        call_count = 0

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise httpx.TimeoutException("timeout")
                return _make_ok_response()

        mock_sleep = AsyncMock()

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.services.proxy.proxy_service.httpx.AsyncClient",
                    return_value=MockAsyncClient(),
                )
            )
            _apply_deps(stack, service, server, session, event, sleep_mock=mock_sleep)
            await service.forward_tool_call(request, agent)

        assert mock_sleep.call_args_list == [call(1), call(2)]

    @pytest.mark.asyncio
    async def test_raises_502_when_all_retries_exhausted(self):
        """After _MAX_RETRIES exhausted, 502 is raised."""
        from fastapi import HTTPException

        service = _make_service()
        agent = _make_agent()
        server = _make_server(agent.org_id)
        session = _make_session(agent.id, agent.org_id)
        event = _make_event()
        request = _make_request()

        call_count = 0

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                nonlocal call_count
                call_count += 1
                raise httpx.TimeoutException("always fails")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.services.proxy.proxy_service.httpx.AsyncClient",
                    return_value=MockAsyncClient(),
                )
            )
            _apply_deps(stack, service, server, session, event)
            with pytest.raises(HTTPException) as exc_info:
                await service.forward_tool_call(request, agent)

        assert exc_info.value.status_code == 502
        assert call_count == _MAX_RETRIES + 1

    @pytest.mark.asyncio
    async def test_retries_on_connect_error(self):
        """ConnectError is also retried, and 502 raised after exhaustion."""
        from fastapi import HTTPException

        service = _make_service()
        agent = _make_agent()
        server = _make_server(agent.org_id)
        session = _make_session(agent.id, agent.org_id)
        event = _make_event()
        request = _make_request()

        call_count = 0

        class MockAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                nonlocal call_count
                call_count += 1
                raise httpx.ConnectError("connection refused")

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.services.proxy.proxy_service.httpx.AsyncClient",
                    return_value=MockAsyncClient(),
                )
            )
            _apply_deps(stack, service, server, session, event)
            with pytest.raises(HTTPException) as exc_info:
                await service.forward_tool_call(request, agent)

        assert exc_info.value.status_code == 502
        assert call_count == _MAX_RETRIES + 1
