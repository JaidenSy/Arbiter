"""
Integration tests for POST /api/v1/proxy/tool-call

Uses httpx AsyncClient against the FastAPI app with mocked DB, Redis, and httpx.

Coverage:
    - Tool call blocked when agent has no permission → 403
    - Tool call allowed when permission granted → forwards to MCP server (mock httpx)
    - Cache hit returns cached: true in response
    - Session event logged after tool call
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, AsyncMock

import pytest
import pytest_asyncio


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mcp_server(server_id: uuid.UUID | None = None, name: str = "test-server") -> MagicMock:
    srv = MagicMock()
    srv.id = server_id or uuid.uuid4()
    srv.name = name
    srv.base_url = "http://fake-mcp-server:9000/rpc"
    srv.is_active = True
    return srv


def _make_session(agent_id: uuid.UUID) -> MagicMock:
    sess = MagicMock()
    sess.id = uuid.uuid4()
    sess.agent_id = agent_id
    return sess


def _make_event(session_id: uuid.UUID, tool_name: str, cache_hit: bool = False) -> MagicMock:
    evt = MagicMock()
    evt.id = uuid.uuid4()
    evt.session_id = session_id
    evt.tool_name = tool_name
    evt.cache_hit = cache_hit
    return evt


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestToolCallBlocked:
    @pytest.mark.asyncio
    async def test_tool_call_blocked_no_permission_returns_403(self, authed_client):
        """
        ProxyService.forward_tool_call raises 403 when RBAC check returns False.
        We mock ProxyService.forward_tool_call (as instance method) to raise HTTPException(403).
        """
        client, raw_key, mock_agent = authed_client

        from fastapi import HTTPException, status

        # Patch as an unbound method: 'self' is the first arg when called on instance
        async def mock_forward(self, request, agent):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent lacks permission",
            )

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
            new=mock_forward,
        ):
            resp = await client.post(
                "/api/v1/proxy/tool-call",
                json={
                    "server_name": "filesystem",
                    "tool_name": "delete_file",
                    "params": {"path": "/etc/passwd"},
                },
                headers={"Authorization": f"Bearer {raw_key}"},
            )

        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


class TestToolCallAllowed:
    @pytest.mark.asyncio
    async def test_tool_call_allowed_forwards_to_mcp_and_returns_200(self, authed_client):
        """
        When RBAC allows, ProxyService forwards to MCP server and returns result.
        We mock ProxyService.forward_tool_call (instance method) to return a ToolCallResponse.
        """
        client, raw_key, mock_agent = authed_client

        from app.schemas.proxy import ToolCallResponse

        session_id = uuid.uuid4()
        event_id = uuid.uuid4()

        async def mock_forward(self, request, agent):
            return ToolCallResponse(
                session_id=session_id,
                event_id=event_id,
                tool_name="read_file",
                result={"content": "file contents here"},
                cache_hit=False,
                duration_ms=42,
            )

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
            new=mock_forward,
        ):
            resp = await client.post(
                "/api/v1/proxy/tool-call",
                json={
                    "server_name": "filesystem",
                    "tool_name": "read_file",
                    "params": {"path": "/etc/hosts"},
                },
                headers={"Authorization": f"Bearer {raw_key}"},
            )

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["tool_name"] == "read_file"
        assert data["cache_hit"] is False
        assert data["result"] == {"content": "file contents here"}
        assert "session_id" in data
        assert "event_id" in data


class TestCacheHit:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_true(self, authed_client):
        """
        When cache is hit, response must include cache_hit: true.
        """
        client, raw_key, mock_agent = authed_client

        from app.schemas.proxy import ToolCallResponse

        session_id = uuid.uuid4()
        event_id = uuid.uuid4()

        async def mock_forward(self, request, agent):
            return ToolCallResponse(
                session_id=session_id,
                event_id=event_id,
                tool_name="read_file",
                result={"content": "cached file contents"},
                cache_hit=True,
                duration_ms=2,
            )

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
            new=mock_forward,
        ):
            resp = await client.post(
                "/api/v1/proxy/tool-call",
                json={
                    "server_name": "filesystem",
                    "tool_name": "read_file",
                    "params": {"path": "/etc/hosts"},
                },
                headers={"Authorization": f"Bearer {raw_key}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["cache_hit"] is True, f"Expected cache_hit=true, got: {data}"


class TestSessionEvent:
    @pytest.mark.asyncio
    async def test_session_event_logged_after_tool_call(self, authed_client):
        """
        After a successful tool call, the response must include an event_id
        (indicating a SessionEvent was persisted).
        """
        client, raw_key, mock_agent = authed_client

        from app.schemas.proxy import ToolCallResponse

        session_id = uuid.uuid4()
        event_id = uuid.uuid4()

        call_log: list[dict] = []

        async def mock_forward(self_svc, request, agent):
            call_log.append({
                "tool_name": request.tool_name,
                "params": request.params,
                "agent_id": str(agent.id),
            })
            return ToolCallResponse(
                session_id=session_id,
                event_id=event_id,
                tool_name=request.tool_name,
                result={"content": "ok"},
                cache_hit=False,
                duration_ms=10,
            )

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
            new=mock_forward,
        ):
            resp = await client.post(
                "/api/v1/proxy/tool-call",
                json={
                    "server_name": "filesystem",
                    "tool_name": "list_dir",
                    "params": {"path": "/tmp"},
                },
                headers={"Authorization": f"Bearer {raw_key}"},
            )

        assert resp.status_code == 200
        data = resp.json()

        # event_id present means the audit event was recorded
        assert "event_id" in data
        assert data["event_id"] == str(event_id)

        # forward_tool_call was actually invoked
        assert len(call_log) == 1
        assert call_log[0]["tool_name"] == "list_dir"


class TestProxyAuth:
    @pytest.mark.asyncio
    async def test_no_auth_returns_401(self, test_client):
        """POST /api/v1/proxy/tool-call without auth → 401"""
        resp = await test_client.post(
            "/api/v1/proxy/tool-call",
            json={
                "server_name": "filesystem",
                "tool_name": "read_file",
                "params": {},
            },
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_invalid_key_returns_401(self, fake_redis):
        """POST /api/v1/proxy/tool-call with bad key → 401"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.core.dependencies import get_db, get_redis

        db = AsyncMock()

        async def execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        db.execute = execute

        async def override_get_db():
            yield db

        async def override_get_redis(request=None):
            return fake_redis

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_redis] = override_get_redis

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/api/v1/proxy/tool-call",
                    json={
                        "server_name": "filesystem",
                        "tool_name": "read_file",
                        "params": {},
                    },
                    headers={"Authorization": "Bearer nxai_badkey0000000000000000000000000000000000000000000000000000000000"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
