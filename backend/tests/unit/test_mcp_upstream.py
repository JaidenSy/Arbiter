"""
Unit tests for the dual-era upstream MCP client (app.services.mcp.upstream)
and its wiring into ProxyService.

httpx is mocked with a scripted fake AsyncClient that records every POST, so
the tests assert on the exact wire traffic:

    - modern server: server/discover probe, then stateless tools/call with
      _meta + MCP-Protocol-Version/Mcp-Method/Mcp-Name; no initialize
    - legacy server: probe falls back, initialize with our newest legacy
      version, notifications/initialized with session + version headers
    - -32022 from a dual-era server -> legacy with a mutually supported version
    - a recognized modern error on the probe does NOT fall back
    - era is cached; a 401 probe is not
    - legacy 404 on a session -> re-initialize once and retry
    - cached-modern server that turns legacy -> re-probe and fall back
    - pre-dual-era cache entries (bare session id strings) still work
"""

from __future__ import annotations

import json
import uuid
from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.mcp import protocol as p
from app.services.mcp.upstream import LEGACY, MODERN, UpstreamMCPClient, UpstreamTarget

URL = "http://upstream.test/mcp"
SERVER_KEY = "server-1:abcd1234"


# ── Fake transport ────────────────────────────────────────────────────────────


class FakeUpstream:
    """Scripted upstream: ``handler(body, headers) -> httpx.Response``."""

    def __init__(self, handler):
        self.handler = handler
        self.calls: list[tuple[dict[str, Any], dict[str, str]]] = []

    def methods(self) -> list[str]:
        return [body.get("method") for body, _ in self.calls]

    def client_factory(self, *args, **kwargs):
        upstream = self

        class _Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return None

            async def post(self, url, json=None, headers=None):
                upstream.calls.append((json, dict(headers or {})))
                return upstream.handler(json, headers or {})

        return _Client()


def _resp(status: int, body: Any = None, headers: dict | None = None) -> httpx.Response:
    request = httpx.Request("POST", URL)
    if body is None:
        return httpx.Response(status, headers=headers, request=request)
    return httpx.Response(status, json=body, headers=headers, request=request)


def _modern_server(body, headers):
    method = body.get("method")
    if method == "server/discover":
        return _resp(
            200,
            {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {
                    "resultType": "complete",
                    "supportedVersions": ["2026-07-28"],
                    "capabilities": {"tools": {}},
                    "ttlMs": 1000,
                    "cacheScope": "public",
                },
            },
        )
    if method == "tools/call":
        return _resp(
            200,
            {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"resultType": "complete", "content": [{"type": "text", "text": "m"}]},
            },
        )
    return _resp(404, {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32601}})


def _legacy_server(session_id: str = "sess-1", negotiated: str = "2025-06-18"):
    state = {"sid": session_id}

    def handler(body, headers):
        method = body.get("method")
        if method == "server/discover":
            # Typical legacy Streamable HTTP server without a session.
            return _resp(
                400,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32000, "message": "Bad Request: No valid session ID"},
                },
            )
        if method == "initialize":
            return _resp(
                200,
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "protocolVersion": negotiated,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "legacy", "version": "1"},
                    },
                },
                headers={"Mcp-Session-Id": state["sid"]},
            )
        if method == "notifications/initialized":
            return _resp(202)
        if headers.get("Mcp-Session-Id") != state["sid"]:
            return _resp(404)
        return _resp(
            200,
            {"jsonrpc": "2.0", "id": body["id"], "result": {"content": [], "tools": []}},
        )

    return handler, state


@pytest.fixture
def client(fake_redis):
    return UpstreamMCPClient(fake_redis, httpx.Timeout(5.0))


def _patch_httpx(fake: FakeUpstream):
    return patch("app.services.mcp.upstream.httpx.AsyncClient", new=fake.client_factory)


# ── Era detection ─────────────────────────────────────────────────────────────


class TestModernServer:
    @pytest.mark.asyncio
    async def test_discover_probe_then_stateless_requests(self, client):
        fake = FakeUpstream(_modern_server)
        with _patch_httpx(fake):
            target = await client.prepare(URL, SERVER_KEY, {"Authorization": "Bearer t"}, "k")

        assert target.era == MODERN
        assert target.protocol_version == "2026-07-28"
        assert fake.methods() == ["server/discover"]

        probe_body, probe_headers = fake.calls[0]
        assert probe_headers["MCP-Protocol-Version"] == "2026-07-28"
        assert probe_headers["Mcp-Method"] == "server/discover"
        assert probe_headers["Authorization"] == "Bearer t"
        assert probe_body["params"]["_meta"][p.META_PROTOCOL_VERSION] == "2026-07-28"
        assert probe_body["params"]["_meta"][p.META_CLIENT_CAPABILITIES] == {}

        body, headers = target.build("tools/call", {"name": "get_weather", "arguments": {}}, 7)
        assert headers["Mcp-Method"] == "tools/call"
        assert headers["Mcp-Name"] == "get_weather"
        assert headers["MCP-Protocol-Version"] == "2026-07-28"
        assert "Mcp-Session-Id" not in headers
        assert body["params"]["_meta"][p.META_PROTOCOL_VERSION] == "2026-07-28"
        assert body["params"]["name"] == "get_weather"

    @pytest.mark.asyncio
    async def test_non_ascii_tool_name_uses_base64_sentinel(self):
        target = UpstreamTarget(MODERN, "2026-07-28", {})
        _, headers = target.build("tools/call", {"name": "wetter_köln"}, 1)
        assert headers["Mcp-Name"].startswith("=?base64?")
        assert p.decode_header_value(headers["Mcp-Name"]) == "wetter_köln"

    @pytest.mark.asyncio
    async def test_era_is_cached(self, client):
        fake = FakeUpstream(_modern_server)
        with _patch_httpx(fake):
            await client.prepare(URL, SERVER_KEY, {}, "k")
            await client.prepare(URL, SERVER_KEY, {}, "k")
        assert fake.methods() == ["server/discover"]

    @pytest.mark.asyncio
    async def test_recognized_modern_error_on_probe_does_not_fall_back(self, client):
        def handler(body, headers):
            return _resp(
                400,
                {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32020, "message": "x"}},
            )

        fake = FakeUpstream(handler)
        with _patch_httpx(fake):
            target = await client.prepare(URL, SERVER_KEY, {}, "k")
        assert target.era == MODERN
        assert "initialize" not in fake.methods()


class TestLegacyFallback:
    @pytest.mark.asyncio
    async def test_falls_back_to_full_legacy_handshake(self, client, fake_redis):
        handler, _ = _legacy_server(negotiated="2025-06-18")
        fake = FakeUpstream(handler)
        with _patch_httpx(fake):
            target = await client.prepare(URL, SERVER_KEY, {"Authorization": "Bearer t"}, "sk")

        assert fake.methods() == ["server/discover", "initialize", "notifications/initialized"]
        init_body, init_headers = fake.calls[1]
        assert init_body["params"]["protocolVersion"] == "2025-11-25"  # our newest legacy
        assert init_headers["Authorization"] == "Bearer t"
        notif_body, notif_headers = fake.calls[2]
        assert "id" not in notif_body
        assert notif_headers["Mcp-Session-Id"] == "sess-1"
        assert notif_headers["MCP-Protocol-Version"] == "2025-06-18"  # negotiated, not ours

        assert target.era == LEGACY
        assert target.session_id == "sess-1"
        assert target.protocol_version == "2025-06-18"
        _, headers = target.build("tools/call", {"name": "t", "arguments": {}}, 1)
        assert headers["Mcp-Session-Id"] == "sess-1"
        assert headers["MCP-Protocol-Version"] == "2025-06-18"
        assert "Mcp-Method" not in headers

        stored = json.loads(await fake_redis.get("sk"))
        assert stored == {"sid": "sess-1", "v": "2025-06-18"}

    @pytest.mark.asyncio
    async def test_cached_session_skips_handshake(self, client):
        handler, _ = _legacy_server()
        fake = FakeUpstream(handler)
        with _patch_httpx(fake):
            await client.prepare(URL, SERVER_KEY, {}, "sk")
            again = await client.prepare(URL, SERVER_KEY, {}, "sk")
        assert fake.methods().count("initialize") == 1
        assert fake.methods().count("server/discover") == 1
        assert again.session_id == "sess-1"

    @pytest.mark.asyncio
    async def test_bare_string_session_from_old_cache_is_reused(self, client, fake_redis):
        await fake_redis.set(
            "mcp_upstream_era:" + SERVER_KEY, json.dumps({"era": "legacy", "version": None})
        )
        await fake_redis.set("sk", "old-session")
        fake = FakeUpstream(lambda b, h: _resp(500))
        with _patch_httpx(fake):
            target = await client.prepare(URL, SERVER_KEY, {}, "sk")
        assert fake.calls == []
        assert target.session_id == "old-session"
        assert target.protocol_version is None

    @pytest.mark.asyncio
    async def test_unsupported_version_error_picks_mutual_legacy_version(self, client):
        def handler(body, headers):
            if body.get("method") == "server/discover":
                return _resp(
                    400,
                    {
                        "jsonrpc": "2.0",
                        "id": body["id"],
                        "error": {
                            "code": -32022,
                            "message": "Unsupported protocol version",
                            "data": {"supported": ["2027-01-01", "2025-03-26"], "requested": "x"},
                        },
                    },
                )
            if body.get("method") == "initialize":
                return _resp(
                    200,
                    {
                        "jsonrpc": "2.0",
                        "id": body["id"],
                        "result": {"protocolVersion": body["params"]["protocolVersion"]},
                    },
                )
            return _resp(202)

        fake = FakeUpstream(handler)
        with _patch_httpx(fake):
            target = await client.prepare(URL, SERVER_KEY, {}, None)
        assert fake.calls[1][0]["params"]["protocolVersion"] == "2025-03-26"
        assert target.era == LEGACY
        assert target.protocol_version == "2025-03-26"

    @pytest.mark.asyncio
    async def test_no_mutual_version_is_502(self, client):
        from fastapi import HTTPException

        def handler(body, headers):
            return _resp(
                400,
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "error": {
                        "code": -32022,
                        "message": "u",
                        "data": {"supported": ["2099-01-01"]},
                    },
                },
            )

        fake = FakeUpstream(handler)
        with _patch_httpx(fake), pytest.raises(HTTPException) as exc:
            await client.prepare(URL, SERVER_KEY, {}, None)
        assert exc.value.status_code == 502

    @pytest.mark.asyncio
    async def test_401_probe_is_not_cached(self, client, fake_redis):
        fake = FakeUpstream(lambda b, h: _resp(401))
        with _patch_httpx(fake):
            target = await client.prepare(URL, SERVER_KEY, {}, None)
        assert target.era == LEGACY
        assert await fake_redis.get("mcp_upstream_era:" + SERVER_KEY) is None

    @pytest.mark.asyncio
    async def test_probe_network_error_degrades_to_legacy(self, client):
        def handler(body, headers):
            if body.get("method") == "server/discover":
                raise httpx.ConnectError("boom")
            return _resp(200, {"jsonrpc": "2.0", "id": body.get("id"), "result": {}})

        fake = FakeUpstream(handler)
        with _patch_httpx(fake):
            target = await client.prepare(URL, SERVER_KEY, {}, None)
        assert target.era == LEGACY
        assert "initialize" in fake.methods()


# ── Recovery ──────────────────────────────────────────────────────────────────


class TestRecovery:
    @pytest.mark.asyncio
    async def test_legacy_404_reinitializes_once(self, client, fake_redis):
        handler, state = _legacy_server(session_id="sess-1")
        fake = FakeUpstream(handler)
        with _patch_httpx(fake):
            target = await client.prepare(URL, SERVER_KEY, {}, "sk")
            state["sid"] = "sess-2"  # upstream restarted; old session gone
            fresh = await client.recover(URL, SERVER_KEY, target, _resp(404))

        assert fresh is not None
        assert fresh.session_id == "sess-2"
        assert fake.methods().count("initialize") == 2
        assert json.loads(await fake_redis.get("sk"))["sid"] == "sess-2"

    @pytest.mark.asyncio
    async def test_legacy_non_404_is_not_recovered(self, client):
        target = UpstreamTarget(LEGACY, "2025-06-18", {}, "sess-1", "sk")
        assert await client.recover(URL, SERVER_KEY, target, _resp(500)) is None

    @pytest.mark.asyncio
    async def test_modern_method_not_found_is_not_recovered(self, client):
        target = UpstreamTarget(MODERN, "2026-07-28", {})
        resp = _resp(404, {"jsonrpc": "2.0", "id": 1, "error": {"code": -32601, "message": "m"}})
        assert await client.recover(URL, SERVER_KEY, target, resp) is None

    @pytest.mark.asyncio
    async def test_cached_modern_server_turned_legacy_is_reprobed(self, client, fake_redis):
        await fake_redis.set(
            "mcp_upstream_era:" + SERVER_KEY, json.dumps({"era": "modern", "version": "2026-07-28"})
        )
        handler, _ = _legacy_server()
        fake = FakeUpstream(handler)
        target = UpstreamTarget(MODERN, "2026-07-28", {"Content-Type": "application/json"})
        with _patch_httpx(fake):
            fresh = await client.recover(URL, SERVER_KEY, target, _resp(400))
        assert fresh is not None
        assert fresh.era == LEGACY
        assert fake.methods() == ["server/discover", "initialize", "notifications/initialized"]


# ── ProxyService wiring ───────────────────────────────────────────────────────


def _make_proxy_deps(stack: ExitStack, service, server, session, event) -> None:
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
    stack.enter_context(  # Pass-through: injected params == request params.
        patch.object(service, "intercept_request", new=AsyncMock(return_value={"p": 1}))
    )
    stack.enter_context(
        patch.object(service, "_ensure_session", new=AsyncMock(return_value=session))
    )
    stack.enter_context(patch.object(service, "_persist_event", new=AsyncMock(return_value=event)))
    stack.enter_context(patch("app.services.proxy.proxy_service.assert_ssrf_safe", new=AsyncMock()))
    stack.enter_context(
        patch("app.services.proxy.proxy_service.PLAN_LIMITS", {"free": {"semantic_cache": False}})
    )


def _proxy_fixtures(fake_redis):
    from app.schemas.proxy import ToolCallRequest
    from app.services.proxy.proxy_service import ProxyService

    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(plan_tier="free", id=uuid.uuid4()))
    service = ProxyService(db, fake_redis)
    agent = MagicMock()
    agent.id = uuid.uuid4()
    agent.org_id = uuid.uuid4()
    agent.name = "a"
    agent.scope = "full"
    agent.rate_limit_per_minute = None
    agent.max_calls_per_session = None
    server = MagicMock()
    server.id = uuid.uuid4()
    server.org_id = agent.org_id
    server.name = "srv"
    server.base_url = URL
    server.headers = {}
    server.cache_enabled = False
    session = MagicMock()
    session.id = uuid.uuid4()
    event = MagicMock()
    event.id = uuid.uuid4()
    request = ToolCallRequest(server_name="srv", tool_name="read_file", params={"p": 1})
    return service, agent, server, session, event, request


class TestProxyServiceWiring:
    @pytest.mark.asyncio
    async def test_forward_tool_call_to_modern_upstream(self, fake_redis):
        service, agent, server, session, event, request = _proxy_fixtures(fake_redis)
        fake = FakeUpstream(_modern_server)
        with ExitStack() as stack:
            _make_proxy_deps(stack, service, server, session, event)
            stack.enter_context(_patch_httpx(fake))
            resp = await service.forward_tool_call(request, agent)

        assert fake.methods() == ["server/discover", "tools/call"]
        body, headers = fake.calls[1]
        assert headers["Mcp-Name"] == "read_file"
        assert body["params"]["arguments"] == {"p": 1}
        assert resp.result["content"][0]["text"] == "m"

    @pytest.mark.asyncio
    async def test_forward_tool_call_reinitializes_on_expired_session(self, fake_redis):
        service, agent, server, session, event, request = _proxy_fixtures(fake_redis)
        handler, state = _legacy_server(session_id="sess-1")
        fake = FakeUpstream(handler)
        with ExitStack() as stack:
            _make_proxy_deps(stack, service, server, session, event)
            stack.enter_context(_patch_httpx(fake))
            await service.forward_tool_call(request, agent)  # establishes sess-1
            state["sid"] = "sess-2"  # session expires upstream
            resp = await service.forward_tool_call(request, agent)

        assert fake.methods() == [
            "server/discover",
            "initialize",
            "notifications/initialized",
            "tools/call",
            "tools/call",  # 404 with sess-1
            "initialize",
            "notifications/initialized",
            "tools/call",  # retried with sess-2
        ]
        assert fake.calls[-1][1]["Mcp-Session-Id"] == "sess-2"
        assert resp.result == {"content": [], "tools": []}

    @pytest.mark.asyncio
    async def test_fetch_tools_list_uses_handshake_for_legacy(self, fake_redis):
        service, agent, server, session, event, request = _proxy_fixtures(fake_redis)
        handler, _ = _legacy_server()
        fake = FakeUpstream(handler)
        with (
            patch("app.services.proxy.proxy_service.assert_ssrf_safe", new=AsyncMock()),
            _patch_httpx(fake),
        ):
            tools = await service.fetch_tools_list(server)
        assert tools == []
        assert fake.methods() == [
            "server/discover",
            "initialize",
            "notifications/initialized",
            "tools/list",
        ]
        assert fake.calls[-1][1]["Mcp-Session-Id"] == "sess-1"
