"""
Enforcement wiring test for ProxyService.forward_tool_call.

tools/list now advertises every tool (RBAC no longer filters the manifest),
so call-time denial in forward_tool_call is the only thing preventing an
unpermitted tool call. This exercises the real
forward_tool_call -> check_permission -> 403 path; only the DB read and the
fire-and-forget webhook dispatch are mocked.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from app.schemas.proxy import ToolCallRequest
from app.services.proxy.proxy_service import ProxyService


def _agent() -> MagicMock:
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.org_id = uuid.uuid4()
    agent.name = "test-agent"
    agent.scope = "full"
    return agent


@pytest.mark.asyncio
async def test_unpermitted_tool_call_denied_at_call_time():
    """No ToolPermission row -> real check_permission returns False -> HTTP 403."""
    agent = _agent()

    # DB EXISTS check returns False -> not permitted.
    db = AsyncMock()

    async def execute(stmt):
        result = MagicMock()
        result.scalar.return_value = False
        return result

    db.execute = execute

    svc = ProxyService(db=db, redis=None)
    request = ToolCallRequest(
        server_name="filesystem",
        tool_name="delete_file",
        params={"path": "/etc/passwd"},
    )

    fake_server = MagicMock()
    fake_server.id = uuid.uuid4()

    with (
        patch.object(ProxyService, "resolve_server", new=AsyncMock(return_value=fake_server)),
        patch("app.services.proxy.proxy_service._dispatch_webhook", new=AsyncMock()),
    ):
        with pytest.raises(HTTPException) as exc:
            await svc.forward_tool_call(request=request, agent=agent)

    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
