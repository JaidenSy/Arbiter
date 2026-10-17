"""
Integration tests for the dual-era native MCP endpoint (POST /mcp).

Modern era (MCP 2026-07-28, stateless):
    - server/discover response shape (supportedVersions, capabilities,
      resultType, ttlMs/cacheScope, serverInfo in _meta)
    - MCP-Protocol-Version / Mcp-Method / Mcp-Name header-vs-body validation
      -> -32020 HeaderMismatch, HTTP 400 (incl. Base64 sentinel decoding)
    - unsupported _meta protocol version -> -32022 with supported/requested
    - missing required _meta fields -> -32602, HTTP 400
    - tools/list: resultType, ttlMs, cacheScope, deterministic order
    - tools/call: resultType, Arbiter session handle via _meta or header,
      no Mcp-Session-Id minted or echoed, non-complete upstream resultType
      surfaced as a tool error
    - unknown / legacy-only methods -> HTTP 404 + -32601

Legacy era (initialize-based):
    - initialize negotiates 2025-11-25 and still mints Mcp-Session-Id
    - MCP-Protocol-Version header validated when present

Transport:
    - Origin allowlist (403 on a present-and-invalid Origin)
    - GET /mcp -> 405
"""

from __future__ import annotations

import base64
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MCP_URL = "/mcp"
MODERN = "2026-07-28"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _modern_meta(version: str = MODERN, **extra) -> dict:
    meta = {
        "io.modelcontextprotocol/protocolVersion": version,
        "io.modelcontextprotocol/clientInfo": {"name": "pytest", "version": "1.0"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    meta.update(extra)
    return meta


def _modern(method: str, params: dict | None = None, req_id: int = 1, **meta_extra) -> dict:
    body_params = dict(params or {})
    body_params["_meta"] = _modern_meta(**meta_extra)
    return {"jsonrpc": "2.0", "id": req_id, "method": method, "params": body_params}


def _modern_headers(method: str, name: str | None = None, version: str = MODERN) -> dict:
    headers = {"MCP-Protocol-Version": version, "Mcp-Method": method}
    if name is not None:
        headers["Mcp-Name"] = name
    return headers


def _make_proxied_response(result: dict | None = None, session_id=None) -> MagicMock:
    resp = MagicMock()
    resp.session_id = session_id or uuid.uuid4()
    resp.event_id = uuid.uuid4()
    resp.cache_hit = False
    resp.duration_ms = 7
    resp.result = result if result is not None else {"content": [{"type": "text", "text": "ok"}]}
    return resp


def _make_server(name: str) -> MagicMock:
    srv = MagicMock()
    srv.id = uuid.uuid4()
    srv.name = name
    srv.base_url = f"http://fake-{name}:9000/rpc"
    srv.is_active = True
    return srv


# ── server/discover ───────────────────────────────────────────────────────────


class TestDiscover:
    @pytest.mark.asyncio
    async def test_discover_returns_versions_capabilities_and_cache_hints(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL, json=_modern("server/discover"), headers=_modern_headers("server/discover")
        )

        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["resultType"] == "complete"
        assert result["supportedVersions"][0] == MODERN
        assert "2025-11-25" in result["supportedVersions"]
        assert "tools" in result["capabilities"]
        assert result["ttlMs"] > 0
        assert result["cacheScope"] == "public"
        assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "arbiter-gateway"
        # Stateless: no protocol session.
        assert "Mcp-Session-Id" not in resp.headers

    @pytest.mark.asyncio
    async def test_discover_without_meta_is_invalid_params(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "server/discover"},
            headers=_modern_headers("server/discover"),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32602


# ── Header validation (-32020) ────────────────────────────────────────────────


class TestHeaderValidation:
    @pytest.mark.asyncio
    async def test_missing_protocol_version_header_is_header_mismatch(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL, json=_modern("server/discover"), headers={"Mcp-Method": "server/discover"}
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == -32020
        assert body["id"] == 1

    @pytest.mark.asyncio
    async def test_protocol_version_header_must_match_meta(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL,
            json=_modern("server/discover"),
            headers=_modern_headers("server/discover", version="2025-11-25"),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32020

    @pytest.mark.asyncio
    async def test_missing_mcp_method_header_is_header_mismatch(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL, json=_modern("tools/list"), headers={"MCP-Protocol-Version": MODERN}
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32020

    @pytest.mark.asyncio
    async def test_mcp_method_header_must_match_body(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL, json=_modern("tools/list"), headers=_modern_headers("server/discover")
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32020

    @pytest.mark.asyncio
    async def test_mcp_name_header_must_match_tool_name(self, authed_client):
        client, _, _ = authed_client

        async def mock_forward(self, request, agent):  # must never run
            raise AssertionError("forwarded despite header mismatch")

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call", new=mock_forward
        ):
            resp = await client.post(
                MCP_URL,
                json=_modern("tools/call", {"name": "github__create_issue", "arguments": {}}),
                headers=_modern_headers("tools/call", name="github__delete_repo"),
            )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"]["code"] == -32020
        assert "Mcp-Name" in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_missing_mcp_name_header_on_tools_call(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL,
            json=_modern("tools/call", {"name": "a__b", "arguments": {}}),
            headers=_modern_headers("tools/call"),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32020

    @pytest.mark.asyncio
    async def test_base64_encoded_mcp_name_is_decoded_before_compare(self, authed_client):
        client, _, _ = authed_client
        tool = "srv__wetter_für_köln"
        encoded = "=?base64?" + base64.b64encode(tool.encode()).decode() + "?="

        async def mock_forward(self, request, agent):
            return _make_proxied_response()

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call", new=mock_forward
        ):
            resp = await client.post(
                MCP_URL,
                json=_modern("tools/call", {"name": tool, "arguments": {}}),
                headers=_modern_headers("tools/call", name=encoded),
            )
        assert resp.status_code == 200
        assert resp.json()["result"]["resultType"] == "complete"

    @pytest.mark.asyncio
    async def test_malformed_base64_mcp_name_is_header_mismatch(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL,
            json=_modern("tools/call", {"name": "a__b", "arguments": {}}),
            headers=_modern_headers("tools/call", name="=?base64?!!!notbase64?="),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32020


# ── Version negotiation (-32022) and required _meta (-32602) ──────────────────


class TestModernVersioning:
    @pytest.mark.asyncio
    async def test_unsupported_meta_version_returns_32022_with_supported_list(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL,
            json=_modern("tools/list", version="2099-01-01"),
            headers=_modern_headers("tools/list", version="2099-01-01"),
        )
        assert resp.status_code == 400
        error = resp.json()["error"]
        assert error["code"] == -32022
        assert error["data"]["requested"] == "2099-01-01"
        assert MODERN in error["data"]["supported"]
        assert "2025-11-25" in error["data"]["supported"]

    @pytest.mark.asyncio
    async def test_missing_client_capabilities_is_invalid_params(self, authed_client):
        client, _, _ = authed_client
        body = _modern("server/discover")
        del body["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"]
        resp = await client.post(MCP_URL, json=body, headers=_modern_headers("server/discover"))
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_modern_header_without_meta_is_invalid_params(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            headers=_modern_headers("tools/list"),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_unknown_method_is_http_404_method_not_found(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL, json=_modern("resources/list"), headers=_modern_headers("resources/list")
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_ping_is_not_a_modern_method(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(MCP_URL, json=_modern("ping"), headers=_modern_headers("ping"))
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == -32601


# ── Modern tools/list ─────────────────────────────────────────────────────────


class TestModernToolsList:
    @pytest.mark.asyncio
    async def test_tools_list_has_cache_hints_and_deterministic_order(self, authed_client):
        client, _, _ = authed_client
        # Returned out of order on purpose; servers also out of order.
        servers = [_make_server("zeta"), _make_server("alpha")]
        upstream_tools = {
            "zeta": [{"name": "b_tool"}, {"name": "a_tool"}],
            "alpha": [{"name": "z_tool"}],
        }

        async def mock_fetch(self, mcp_server):
            return upstream_tools[mcp_server.name]

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
                first = await client.post(
                    MCP_URL, json=_modern("tools/list"), headers=_modern_headers("tools/list")
                )
                # Second call is served from the Redis cache: order must hold.
                second = await client.post(
                    MCP_URL, json=_modern("tools/list"), headers=_modern_headers("tools/list")
                )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert first.status_code == 200
        result = first.json()["result"]
        names = [t["name"] for t in result["tools"]]
        assert names == ["alpha__z_tool", "zeta__a_tool", "zeta__b_tool"]
        assert result["resultType"] == "complete"
        assert result["ttlMs"] == 60_000
        assert result["cacheScope"] == "private"
        assert [t["name"] for t in second.json()["result"]["tools"]] == names


# ── Modern tools/call + Arbiter session handle ────────────────────────────────


class TestModernToolsCall:
    @pytest.mark.asyncio
    async def test_session_handle_from_meta_reaches_pipeline_and_is_returned(self, authed_client):
        client, _, _ = authed_client
        handle = uuid.uuid4()
        captured: dict = {}

        async def mock_forward(self, request, agent):
            captured["request"] = request
            return _make_proxied_response(session_id=handle)

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call", new=mock_forward
        ):
            resp = await client.post(
                MCP_URL,
                json=_modern(
                    "tools/call",
                    {"name": "github__create_issue", "arguments": {"title": "x"}},
                    **{"dev.arbiterai/sessionId": str(handle)},
                ),
                headers={
                    **_modern_headers("tools/call", name="github__create_issue"),
                    # A stale legacy header must be ignored in the modern era.
                    "Mcp-Session-Id": str(uuid.uuid4()),
                },
            )

        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["resultType"] == "complete"
        assert result["content"] == [{"type": "text", "text": "ok"}]
        assert result["_meta"]["dev.arbiterai/sessionId"] == str(handle)
        assert result["_meta"]["arbiter"]["session_id"] == str(handle)
        assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "arbiter-gateway"
        assert captured["request"].session_id == handle
        assert captured["request"].server_name == "github"
        assert "Mcp-Session-Id" not in resp.headers

    @pytest.mark.asyncio
    async def test_session_handle_from_header(self, authed_client):
        client, _, _ = authed_client
        handle = uuid.uuid4()
        captured: dict = {}

        async def mock_forward(self, request, agent):
            captured["request"] = request
            return _make_proxied_response(session_id=handle)

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call", new=mock_forward
        ):
            await client.post(
                MCP_URL,
                json=_modern("tools/call", {"name": "a__b", "arguments": {}}),
                headers={
                    **_modern_headers("tools/call", name="a__b"),
                    "X-Arbiter-Session-Id": str(handle),
                },
            )
        assert captured["request"].session_id == handle

    @pytest.mark.asyncio
    async def test_no_handle_means_new_session(self, authed_client):
        client, _, _ = authed_client
        captured: dict = {}

        async def mock_forward(self, request, agent):
            captured["request"] = request
            return _make_proxied_response()

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call", new=mock_forward
        ):
            await client.post(
                MCP_URL,
                json=_modern("tools/call", {"name": "a__b", "arguments": {}}),
                headers={
                    **_modern_headers("tools/call", name="a__b"),
                    "Mcp-Session-Id": str(uuid.uuid4()),
                },
            )
        assert captured["request"].session_id is None

    @pytest.mark.asyncio
    async def test_gateway_denial_is_iserror_with_result_type(self, authed_client):
        client, _, _ = authed_client
        from fastapi import HTTPException

        async def mock_forward(self, request, agent):
            raise HTTPException(status_code=403, detail="denied")

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call", new=mock_forward
        ):
            resp = await client.post(
                MCP_URL,
                json=_modern("tools/call", {"name": "a__b", "arguments": {}}),
                headers=_modern_headers("tools/call", name="a__b"),
            )
        result = resp.json()["result"]
        assert result["isError"] is True
        assert result["resultType"] == "complete"

    @pytest.mark.asyncio
    async def test_upstream_input_required_is_surfaced_as_tool_error(self, authed_client):
        client, _, _ = authed_client

        async def mock_forward(self, request, agent):
            return _make_proxied_response(
                result={"resultType": "input_required", "inputRequests": {}, "requestState": "x"}
            )

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call", new=mock_forward
        ):
            resp = await client.post(
                MCP_URL,
                json=_modern("tools/call", {"name": "a__b", "arguments": {}}),
                headers=_modern_headers("tools/call", name="a__b"),
            )
        result = resp.json()["result"]
        assert result["isError"] is True
        assert result["resultType"] == "complete"
        assert "input_required" in result["content"][0]["text"]


# ── Legacy era ────────────────────────────────────────────────────────────────


class TestLegacyEra:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("version", ["2025-11-25", "2025-06-18", "2025-03-26"])
    async def test_initialize_negotiates_legacy_versions(self, authed_client, version):
        client, _, _ = authed_client
        session = MagicMock()
        session.id = uuid.uuid4()

        async def mock_create_session(self, agent):
            return session

        with patch(
            "app.services.proxy.proxy_service.ProxyService.create_session",
            new=mock_create_session,
        ):
            resp = await client.post(
                MCP_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": version, "capabilities": {}},
                },
            )
        assert resp.status_code == 200
        assert resp.json()["result"]["protocolVersion"] == version
        assert "resultType" not in resp.json()["result"]
        assert resp.headers["Mcp-Session-Id"] == str(session.id)

    @pytest.mark.asyncio
    async def test_legacy_request_with_valid_protocol_header(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"MCP-Protocol-Version": "2025-11-25"},
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == {}

    @pytest.mark.asyncio
    async def test_legacy_request_with_unknown_protocol_header_is_400(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"MCP-Protocol-Version": "1999-01-01"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == -32022

    @pytest.mark.asyncio
    async def test_legacy_tools_call_still_echoes_session_header(self, authed_client):
        client, _, _ = authed_client
        sid = uuid.uuid4()
        captured: dict = {}

        async def mock_forward(self, request, agent):
            captured["request"] = request
            return _make_proxied_response(session_id=sid)

        with patch(
            "app.services.proxy.proxy_service.ProxyService.forward_tool_call", new=mock_forward
        ):
            resp = await client.post(
                MCP_URL,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "a__b", "arguments": {}},
                },
                headers={"Mcp-Session-Id": str(sid), "MCP-Protocol-Version": "2025-06-18"},
            )
        assert resp.status_code == 200
        assert resp.headers["Mcp-Session-Id"] == str(sid)
        assert captured["request"].session_id == sid
        assert "resultType" not in resp.json()["result"]


# ── Origin validation + transport ─────────────────────────────────────────────


class TestOriginAndTransport:
    @pytest.mark.asyncio
    async def test_disallowed_origin_is_403(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Origin": "https://evil.example"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_disallowed_origin_is_403_before_auth(self, test_client):
        resp = await test_client.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Origin": "https://evil.example"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_cors_origin_is_allowed_by_default(self, authed_client):
        client, _, _ = authed_client
        resp = await client.post(
            MCP_URL,
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_configured_allowlist_overrides_cors(self, authed_client):
        client, _, _ = authed_client
        from app.core.config import settings

        with patch.object(settings, "mcp_allowed_origins", "https://inspector.example"):
            ok = await client.post(
                MCP_URL,
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={"Origin": "https://inspector.example"},
            )
            blocked = await client.post(
                MCP_URL,
                json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                headers={"Origin": "http://localhost:3000"},
            )
        assert ok.status_code == 200
        assert blocked.status_code == 403

    @pytest.mark.asyncio
    async def test_key_in_url_variant_also_validates_origin(self, test_client):
        resp = await test_client.post(
            "/mcp/nxai_whatever",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Origin": "https://evil.example"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_get_is_method_not_allowed(self, authed_client):
        client, _, _ = authed_client
        resp = await client.get(MCP_URL)
        assert resp.status_code == 405
