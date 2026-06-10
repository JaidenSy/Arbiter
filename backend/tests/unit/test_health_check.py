"""
Unit tests for MCP server health monitoring (#208).

Verifies:
    - _probe_server returns (True, latency, None) on success
    - _probe_server returns (False, None, error) on httpx exception
    - Circuit breaker deactivates server after CIRCUIT_BREAKER_THRESHOLD failures
    - Successful probe resets the circuit breaker counter
"""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Import ALL ORM models so SQLAlchemy can finalize all relationship configurations.
# Running the module in isolation skips the normal app import chain, causing
# "mapper failed to initialize" errors when select() triggers lazy configuration.
import app.db.models.agent  # noqa: F401
import app.db.models.cache  # noqa: F401
import app.db.models.cli_device_code  # noqa: F401
import app.db.models.gdpr_deletion_log  # noqa: F401
import app.db.models.mcp_server  # noqa: F401
import app.db.models.mcp_server_health_check  # noqa: F401
import app.db.models.org_invite  # noqa: F401
import app.db.models.organization  # noqa: F401
import app.db.models.refresh_token  # noqa: F401
import app.db.models.session  # noqa: F401
import app.db.models.social_account  # noqa: F401
import app.db.models.tool_permission  # noqa: F401
import app.db.models.tool_permission_event  # noqa: F401
import app.db.models.usage_event  # noqa: F401
import app.db.models.user  # noqa: F401
import app.db.models.vault  # noqa: F401
from app.tasks.health_check import (
    _CIRCUIT_KEY,
    CIRCUIT_BREAKER_THRESHOLD,
    _probe_server,
    run_health_checks,
)

# ── _probe_server unit tests ──────────────────────────────────────────────────


class TestProbeServer:
    @pytest.mark.asyncio
    async def test_healthy_server_returns_true_with_latency(self):
        """Successful tools/list → (True, latency_ms > 0, None)."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {}

        class MockClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                return mock_resp

        with patch("app.tasks.health_check.httpx.AsyncClient", return_value=MockClient()):
            is_healthy, latency_ms, error = await _probe_server("http://fake-mcp:9000", {})

        assert is_healthy is True
        assert latency_ms is not None and latency_ms >= 0
        assert error is None

    @pytest.mark.asyncio
    async def test_timeout_returns_false_with_error(self):
        """TimeoutException → (False, None, error string)."""

        class MockClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                raise httpx.TimeoutException("timeout")

        with patch("app.tasks.health_check.httpx.AsyncClient", return_value=MockClient()):
            is_healthy, latency_ms, error = await _probe_server("http://fake-mcp:9000", {})

        assert is_healthy is False
        assert latency_ms is None
        assert error is not None and "timeout" in error.lower()

    @pytest.mark.asyncio
    async def test_connect_error_returns_false(self):
        """ConnectError → (False, None, error string)."""

        class MockClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            async def post(self, *a, **kw):
                raise httpx.ConnectError("refused")

        with patch("app.tasks.health_check.httpx.AsyncClient", return_value=MockClient()):
            is_healthy, latency_ms, error = await _probe_server("http://fake-mcp:9000", {})

        assert is_healthy is False
        assert latency_ms is None


# ── Circuit breaker tests ─────────────────────────────────────────────────────


def _make_server() -> MagicMock:
    s = MagicMock()
    s.id = uuid.uuid4()
    s.org_id = uuid.uuid4()
    s.name = "test-server"
    s.base_url = "http://fake:9000"
    s.headers = {}
    s.is_active = True
    return s


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_circuit_breaker_deactivates_server_after_threshold(self):
        """After CIRCUIT_BREAKER_THRESHOLD consecutive failures, server is deactivated."""
        server = _make_server()

        redis = AsyncMock()
        redis.incr = AsyncMock(return_value=CIRCUIT_BREAKER_THRESHOLD)
        redis.expire = AsyncMock()
        redis.delete = AsyncMock()

        db = AsyncMock()

        # Simulate: scalars().all() returns [server], then subsequent DB sessions per server
        async def fake_session_factory():
            return db

        class FakeSession:
            async def __aenter__(self):
                return db

            async def __aexit__(self, *_):
                pass

        with ExitStack() as stack:
            # Mock the async_session_factory context manager
            stack.enter_context(
                patch("app.tasks.health_check.async_session_factory", return_value=FakeSession())
            )
            # Mock server query
            servers_result = MagicMock()
            servers_result.scalars.return_value.all.return_value = [server]
            db.execute = AsyncMock(return_value=servers_result)
            db.add = MagicMock()
            db.commit = AsyncMock()
            db.rollback = AsyncMock()

            # Mock vault (no headers)
            with patch("app.tasks.health_check.VaultService"):
                # Mock probe → always fails
                with patch(
                    "app.tasks.health_check._probe_server", return_value=(False, None, "timed out")
                ):
                    await run_health_checks(redis=redis)

        # Verify Redis incr was called and circuit breaker check was applied
        redis.incr.assert_awaited()

    @pytest.mark.asyncio
    async def test_successful_probe_resets_circuit_counter(self):
        """Healthy probe deletes the circuit breaker counter in Redis."""
        server = _make_server()

        redis = AsyncMock()
        redis.delete = AsyncMock()
        redis.incr = AsyncMock()

        db = AsyncMock()

        class FakeSession:
            async def __aenter__(self):
                return db

            async def __aexit__(self, *_):
                pass

        servers_result = MagicMock()
        servers_result.scalars.return_value.all.return_value = [server]
        db.execute = AsyncMock(return_value=servers_result)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        with ExitStack() as stack:
            stack.enter_context(
                patch("app.tasks.health_check.async_session_factory", return_value=FakeSession())
            )
            with patch("app.tasks.health_check.VaultService"):
                with patch("app.tasks.health_check._probe_server", return_value=(True, 120, None)):
                    await run_health_checks(redis=redis)

        # circuit key should be deleted on success
        circuit_key = _CIRCUIT_KEY.format(server_id=str(server.id))
        redis.delete.assert_awaited_with(circuit_key)
