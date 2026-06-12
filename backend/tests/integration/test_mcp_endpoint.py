"""
Integration tests for the native MCP endpoint (POST /mcp).

Uses httpx AsyncClient against the FastAPI app with mocked DB, Redis, and
ProxyService internals.

Coverage:
    - JSON-RPC envelope: parse errors, batch rejection, missing method, unknown method
    - initialize: protocol version negotiation, Mcp-Session-Id header, serverInfo
    - notifications acknowledged with 202
    - ping
    - tools/list: aggregation across servers, namespacing, RBAC filter wiring,
      per-agent Redis cache (read + write), failing upstream skipped
    - tools/call: namespaced routing into ProxyService.forward_tool_call,
      session header propagation, _meta.arbiter passthrough, gateway errors
      (HTTPException / QuotaExceededError / SessionBudgetExceededError) mapped
      to MCP isError: true tool results per the MCP spec
    - key-in-URL variant: auth success and 401
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import TEST_AGENT_ID

MCP_URL = "/mcp"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _rpc(method: str, params: dict | None = None, req_id: int | str | None = 1) -> dict:
    body: dict = {"jsonrpc": "2.0", "method": method}
    if req_id is not None:
        body["id"] = req_id
    if params is not None:
        body["params"] = params
    return body


def _make_session(session_id: uuid.UUID | None = None) -> MagicMock:
    sess = MagicMock()
    sess.id = session_id or uuid.uuid4()
    return sess


def _make_proxied_response(result: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.session_id = uuid.uuid4()
    resp.event_id = uuid.uuid4()
    resp.cache_hit = False
    resp.duration_ms = 42
    resp.result = result if result is not None else {"content": [{"type": "text", "text": "ok"}]}
    return resp


def _make_server(name: str) -> MagicMock:
    srv = MagicMock()
    srv.id = uuid.uuid4()
    srv.name = name
    srv.base_url = f"http://fake-{name}:9000/rpc"
    srv.is_active = True
    return srv


# ── JSON-RPC envelope ─────────────────────────────────────────────────────────


class TestEnvelope:
    @pytest.mark.asyncio
    async def test_invalid_json_returns_parse_error(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL, content=b"{not json", headers={"Content-Type": "application/json"}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32700

    @pytest.mark.asyncio
    async def test_batch_array_rejected(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(MCP_URL, json=[_rpc("ping")])
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_missing_method_is_invalid_request(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(MCP_URL, json={"jsonrpc": "2.0", "id": 1})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_unknown_method_returns_method_not_found(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(MCP_URL, json=_rpc("resources/list"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["error"]["code"] == -32601
        assert body["id"] == 1

    @pytest.mark.asyncio
    async def test_notification_acknowledged_with_202(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(MCP_URL, json=_rpc("notifications/initialized", req_id=None))
        assert resp.status_code == 202
        assert resp.content == b""

    @pytest.mark.asyncio
    async def test_request_without_id_treated_as_notification(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(MCP_URL, json=_rpc("tools/list", req_id=None))
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_id_bearing_notification_method_gets_method_not_found(self, authed_client):
        # An id-bearing message is a request per JSON-RPC 2.0, even with a
        # notifications/ method — it must get a reply, not a silent 202.
        client, _, _ = authed_client
        resp = await client.post(MCP_URL, json=_rpc("notifications/initialized", req_id=7))
        assert resp.status_code == 200
        assert resp.json()["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_jsonrpc_internal_error(self, authed_client):
        client, _, _ = authed_client

        async def mock_forward(self, request, agent):
            raise RuntimeError("db exploded")

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
            new=mock_forward,
        ):
            resp = await client.post(
                MCP_URL, json=_rpc("tools/call", {"name": "a__b", "arguments": {}})
            )

        assert resp.status_code == 200
        assert resp.json()["error"]["code"] == -32603

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, test_client):
        resp = await test_client.post(MCP_URL, json=_rpc("ping"))
        assert resp.status_code == 401


# ── initialize / ping ─────────────────────────────────────────────────────────


class TestInitialize:
    @pytest.mark.asyncio
    async def test_initialize_returns_serverinfo_and_session_header(self, authed_client):
        client, _, _ = authed_client
        session = _make_session()

        async def mock_create_session(self, agent):
            return session

        with patch(
            "app.services.proxy.proxy_service.ProxyService.create_session",
            new=mock_create_session,
        ):
            resp = await client.post(
                MCP_URL,
                json=_rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}}),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["protocolVersion"] == "2025-03-26"
        assert body["result"]["serverInfo"]["name"] == "arbiter-gateway"
        assert "tools" in body["result"]["capabilities"]
        assert resp.headers["Mcp-Session-Id"] == str(session.id)

    @pytest.mark.asyncio
    async def test_initialize_unsupported_version_answers_with_latest(self, authed_client):
        client, _, _ = authed_client

        async def mock_create_session(self, agent):
            return _make_session()

        with patch(
            "app.services.proxy.proxy_service.ProxyService.create_session",
            new=mock_create_session,
        ):
            resp = await client.post(
                MCP_URL, json=_rpc("initialize", {"protocolVersion": "1999-01-01"})
            )

        assert resp.json()["result"]["protocolVersion"] == "2025-06-18"

    @pytest.mark.asyncio
    async def test_ping_returns_empty_result(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(MCP_URL, json=_rpc("ping"))
        assert resp.status_code == 200
        assert resp.json() == {"jsonrpc": "2.0", "id": 1, "result": {}}


# ── tools/list ────────────────────────────────────────────────────────────────


class TestToolsList:
    @pytest.mark.asyncio
    async def test_aggregates_and_namespaces_across_servers(self, authed_client, fake_redis):
        client, _, _ = authed_client
        servers = [_make_server("github"), _make_server("filesystem")]
        upstream_tools = {
            "github": [{"name": "create_issue", "description": "create"}],
            "filesystem": [{"name": "read_file", "description": "read"}],
        }

        async def mock_fetch(self, mcp_server):
            return upstream_tools[mcp_server.name]

        async def mock_filter(self, agent, server_name, tools, mcp_server=None):
            return tools  # RBAC allows everything in this test

        # The endpoint queries MCPServer rows via the (mocked) db session.
        scalars = MagicMock()
        scalars.all.return_value = servers
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars

        from app.core.dependencies import get_db
        from app.main import app

        async def _override_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=exec_result)
            yield db

        app.dependency_overrides[get_db] = _override_get_db
        try:
            with (
                patch(
                    "app.services.proxy.proxy_service.ProxyService.fetch_tools_list",
                    new=mock_fetch,
                ),
                patch(
                    "app.services.proxy.proxy_service.ProxyService.filter_tools_list",
                    new=mock_filter,
                ),
            ):
                resp = await client.post(MCP_URL, json=_rpc("tools/list"))
        finally:
            # restore the fixture's own get_db override for remaining requests
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        names = sorted(t["name"] for t in resp.json()["result"]["tools"])
        assert names == ["filesystem__read_file", "github__create_issue"]

        # Result must be cached per-agent in Redis.
        cached = await fake_redis.get(f"mcp_tools_list:{TEST_AGENT_ID}")
        assert cached is not None
        assert len(json.loads(cached)) == 2

    @pytest.mark.asyncio
    async def test_cache_hit_skips_upstream(self, authed_client, fake_redis):
        client, _, _ = authed_client
        cached_tools = [{"name": "github__create_issue"}]
        await fake_redis.setex(f"mcp_tools_list:{TEST_AGENT_ID}", 60, json.dumps(cached_tools))

        async def mock_fetch(self, mcp_server):  # must never be called
            raise AssertionError("upstream fetched despite cache hit")

        with patch(
            "app.services.proxy.proxy_service.ProxyService.fetch_tools_list", new=mock_fetch
        ):
            resp = await client.post(MCP_URL, json=_rpc("tools/list"))

        assert resp.json()["result"]["tools"] == cached_tools

    @pytest.mark.asyncio
    async def test_unreachable_server_is_skipped(self, authed_client):
        client, _, _ = authed_client
        from fastapi import HTTPException

        servers = [_make_server("up"), _make_server("down")]

        async def mock_fetch(self, mcp_server):
            if mcp_server.name == "down":
                raise HTTPException(status_code=502, detail="unreachable")
            return [{"name": "tool_a"}]

        async def mock_filter(self, agent, server_name, tools, mcp_server=None):
            return tools

        scalars = MagicMock()
        scalars.all.return_value = servers
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars

        from app.core.dependencies import get_db
        from app.main import app

        async def _override_get_db():
            db = AsyncMock()
            db.execute = AsyncMock(return_value=exec_result)
            yield db

        app.dependency_overrides[get_db] = _override_get_db
        try:
            with (
                patch(
                    "app.services.proxy.proxy_service.ProxyService.fetch_tools_list",
                    new=mock_fetch,
                ),
                patch(
                    "app.services.proxy.proxy_service.ProxyService.filter_tools_list",
                    new=mock_filter,
                ),
            ):
                resp = await client.post(MCP_URL, json=_rpc("tools/list"))
        finally:
            app.dependency_overrides.pop(get_db, None)

        names = [t["name"] for t in resp.json()["result"]["tools"]]
        assert names == ["up__tool_a"]


# ── tools/call ────────────────────────────────────────────────────────────────


class TestToolsCall:
    @pytest.mark.asyncio
    async def test_routes_namespaced_call_through_pipeline(self, authed_client):
        client, _, _ = authed_client
        proxied = _make_proxied_response()
        captured: dict = {}

        async def mock_forward(self, request, agent):
            captured["request"] = request
            return proxied

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
            new=mock_forward,
        ):
            resp = await client.post(
                MCP_URL,
                json=_rpc(
                    "tools/call",
                    {"name": "github__create_issue", "arguments": {"title": "hi"}},
                ),
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["content"] == [{"type": "text", "text": "ok"}]
        # Gateway observability attached under the spec's _meta extension point.
        meta = body["result"]["_meta"]["arbiter"]
        assert meta["cache_hit"] is False
        assert meta["duration_ms"] == 42
        assert resp.headers["Mcp-Session-Id"] == str(proxied.session_id)
        # Namespace split: first "__" separates server from tool.
        assert captured["request"].server_name == "github"
        assert captured["request"].tool_name == "create_issue"
        assert captured["request"].params == {"title": "hi"}

    @pytest.mark.asyncio
    async def test_session_header_propagates_to_pipeline(self, authed_client):
        client, _, _ = authed_client
        session_id = uuid.uuid4()
        captured: dict = {}

        async def mock_forward(self, request, agent):
            captured["request"] = request
            return _make_proxied_response()

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
            new=mock_forward,
        ):
            await client.post(
                MCP_URL,
                json=_rpc("tools/call", {"name": "a__b", "arguments": {}}),
                headers={"Mcp-Session-Id": str(session_id)},
            )

        assert captured["request"].session_id == session_id

    @pytest.mark.asyncio
    async def test_non_namespaced_tool_name_is_invalid_params(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL, json=_rpc("tools/call", {"name": "create_issue", "arguments": {}})
        )
        assert resp.status_code == 200
        assert resp.json()["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_empty_tool_after_separator_is_invalid_params(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL, json=_rpc("tools/call", {"name": "github__", "arguments": {}})
        )
        assert resp.json()["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_non_dict_arguments_is_invalid_params(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL, json=_rpc("tools/call", {"name": "a__b", "arguments": "not-a-dict"})
        )
        assert resp.json()["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_rbac_denial_returns_iserror_result(self, authed_client):
        """RBAC 403 must return isError: true tool result, not a protocol error."""
        client, _, _ = authed_client
        from fastapi import HTTPException

        async def mock_forward(self, request, agent):
            raise HTTPException(status_code=403, detail="Agent lacks permission")

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
            new=mock_forward,
        ):
            resp = await client.post(
                MCP_URL, json=_rpc("tools/call", {"name": "a__b", "arguments": {}})
            )

        assert resp.status_code == 200
        body = resp.json()
        # Must be a successful JSON-RPC result envelope, not an error envelope.
        assert "error" not in body
        result = body["result"]
        assert result["isError"] is True
        assert result["content"][0]["type"] == "text"
        assert "permission" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_quota_exceeded_returns_iserror_result(self, authed_client):
        """Quota exceeded must return isError: true, not a protocol error."""
        client, _, _ = authed_client
        from app.services.plan.plan_limits import QuotaExceededError

        async def mock_forward(self, request, agent):
            raise QuotaExceededError(
                resource="tool_calls",
                used=5000,
                limit=5000,
                resets_at=datetime(2026, 7, 1, tzinfo=UTC),
            )

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
            new=mock_forward,
        ):
            resp = await client.post(
                MCP_URL, json=_rpc("tools/call", {"name": "a__b", "arguments": {}})
            )

        body = resp.json()
        assert "error" not in body
        result = body["result"]
        assert result["isError"] is True
        assert "quota" in result["content"][0]["text"].lower()

    @pytest.mark.asyncio
    async def test_session_budget_returns_iserror_result(self, authed_client):
        """Session budget exceeded must return isError: true, not a protocol error."""
        client, _, _ = authed_client
        from app.services.plan.plan_limits import SessionBudgetExceededError

        async def mock_forward(self, request, agent):
            raise SessionBudgetExceededError(session_id=str(uuid.uuid4()), used=11, limit=10)

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call",
            new=mock_forward,
        ):
            resp = await client.post(
                MCP_URL, json=_rpc("tools/call", {"name": "a__b", "arguments": {}})
            )

        body = resp.json()
        assert "error" not in body
        result = body["result"]
        assert result["isError"] is True
        assert "budget" in result["content"][0]["text"].lower()


# ── key-in-URL variant ────────────────────────────────────────────────────────


class TestKeyInUrl:
    @pytest.mark.asyncio
    async def test_valid_key_in_url_authenticates(self, authed_client):
        client, raw_key, mock_agent = authed_client

        async def mock_resolve(api_key, db):
            assert api_key == raw_key
            return mock_agent

        async def mock_verified(agent, db, redis):
            return None

        with (
            patch("app.api.v1.endpoints.mcp.resolve_agent_by_api_key", new=mock_resolve),
            patch("app.api.v1.endpoints.mcp.ensure_org_verified", new=mock_verified),
        ):
            resp = await client.post(f"/mcp/{raw_key}", json=_rpc("ping"))

        assert resp.status_code == 200
        assert resp.json()["result"] == {}

    @pytest.mark.asyncio
    async def test_invalid_key_in_url_returns_401(self, test_client):
        from fastapi import HTTPException

        async def mock_resolve(api_key, db):
            raise HTTPException(status_code=401, detail="Invalid or inactive API key")

        with patch("app.api.v1.endpoints.mcp.resolve_agent_by_api_key", new=mock_resolve):
            resp = await test_client.post("/mcp/nxai_bogus", json=_rpc("ping"))

        assert resp.status_code == 401
