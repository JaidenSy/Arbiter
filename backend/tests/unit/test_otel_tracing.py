"""
Unit tests for OpenTelemetry tracing (app/core/telemetry.py + /mcp + ProxyService).

Uses the SDK's InMemorySpanExporter to assert, for a mocked tools/call that
runs through the real ProxyService.forward_tool_call pipeline:
    - SERVER span name + MCP/GenAI semconv attributes
    - parent from params._meta, HTTP traceparent attached as a link
    - fallback to the HTTP traceparent header when _meta has no context
    - pipeline-stage child spans (rbac, rate limit, cache lookup, quota,
      vault injection) and the upstream CLIENT span, all parented correctly
    - traceparent injected into the upstream tools/call params._meta
    - error.type on RBAC denial (tool_error) and upstream JSON-RPC errors
    - tool arguments/results and secrets never recorded by default
And that everything is a no-op when tracing is disabled.
"""

from __future__ import annotations

import json
import uuid
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind
from opentelemetry.util._once import Once

from app.core import telemetry

MCP_URL = "/mcp"

# A "client" (e.g. Claude Code) span carried in params._meta ...
CLIENT_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
CLIENT_SPAN_ID = "00f067aa0ba902b7"
META_TRACEPARENT = f"00-{CLIENT_TRACE_ID}-{CLIENT_SPAN_ID}-01"
# ... and an unrelated HTTP transport context in the request headers.
HTTP_TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
HTTP_SPAN_ID = "b7ad6b7169203331"
HTTP_TRACEPARENT = f"00-{HTTP_TRACE_ID}-{HTTP_SPAN_ID}-01"

SECRET_VALUE = "s3cret-value-never-in-spans"


# ── Fixtures / helpers ────────────────────────────────────────────────────────


def _reset_otel_globals() -> None:
    """Allow a fresh global TracerProvider per test (the API sets it only once)."""
    trace._TRACER_PROVIDER_SET_ONCE = Once()
    trace._TRACER_PROVIDER = None


@pytest.fixture
def span_exporter():
    """Enable tracing with an in-memory exporter for one test."""
    _reset_otel_globals()
    exporter = InMemorySpanExporter()
    assert telemetry.configure_telemetry(otel_enabled=True, span_exporter=exporter)
    yield exporter
    telemetry.shutdown_telemetry()
    _reset_otel_globals()


@pytest.fixture
def tracing_disabled():
    """Make sure no provider is installed and telemetry reports disabled."""
    telemetry.shutdown_telemetry()
    _reset_otel_globals()
    yield
    _reset_otel_globals()


class _UpstreamCapture:
    """Stands in for httpx.AsyncClient; records the outbound JSON-RPC body."""

    def __init__(self, response_json: dict) -> None:
        self.bodies: list[dict] = []
        self._response_json = response_json

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):  # noqa: A002 - mirrors httpx
        self.bodies.append(json)
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"content-type": "application/json"}
        resp.json.return_value = self._response_json
        resp.text = ""
        return resp


@contextmanager
def _pipeline(
    agent,
    *,
    permitted: bool = True,
    cached: dict | None = None,
    upstream_json: dict | None = None,
):
    """Patch ProxyService's I/O so the real forward_tool_call pipeline runs."""
    agent.org_id = uuid.uuid4()
    agent.scope = "full"
    agent.rate_limit_per_minute = None
    agent.max_calls_per_session = None

    server = MagicMock()
    server.id = uuid.uuid4()
    server.name = "github"
    server.base_url = "https://mcp.example.com:8443/rpc?token=nope"
    server.headers = {}
    server.cache_enabled = True
    server.cost_per_call_usd = None

    session = MagicMock()
    session.id = uuid.uuid4()
    event = MagicMock()
    event.id = uuid.uuid4()

    upstream = _UpstreamCapture(
        upstream_json
        if upstream_json is not None
        else {"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": "ok"}]}}
    )
    ps = "app.services.proxy.proxy_service"
    with ExitStack() as stack:
        enter = stack.enter_context
        enter(patch(f"{ps}.ProxyService.resolve_server", new=AsyncMock(return_value=server)))
        enter(patch(f"{ps}.ProxyService._ensure_session", new=AsyncMock(return_value=session)))
        enter(patch(f"{ps}.ProxyService._persist_event", new=AsyncMock(return_value=event)))
        enter(patch(f"{ps}.ProxyService._ensure_mcp_session", new=AsyncMock(return_value={})))
        enter(patch(f"{ps}.RBACService.check_permission", new=AsyncMock(return_value=permitted)))
        enter(patch(f"{ps}.RBACService.get_rate_limit", new=AsyncMock(return_value=None)))
        enter(patch(f"{ps}.RBACService.get_cache_ttl", new=AsyncMock(return_value=None)))
        enter(patch(f"{ps}.CacheService.get_cached", new=AsyncMock(return_value=cached)))
        enter(patch(f"{ps}.CacheService.store_cached", new=AsyncMock()))
        enter(patch(f"{ps}.VaultService.get_secret", new=AsyncMock(return_value=SECRET_VALUE)))
        enter(patch(f"{ps}.check_tool_call_quota", new=AsyncMock()))
        enter(patch(f"{ps}.assert_ssrf_safe", new=AsyncMock()))
        enter(patch(f"{ps}._dispatch_webhook", new=AsyncMock()))
        enter(patch(f"{ps}.httpx.AsyncClient", new=upstream))
        yield upstream


def _tools_call(meta: dict | None = None, arguments: dict | None = None, req_id=7) -> dict:
    params: dict = {
        "name": "github__create_issue",
        "arguments": arguments if arguments is not None else {"title": "hi"},
    }
    if meta is not None:
        params["_meta"] = meta
    return {"jsonrpc": "2.0", "id": req_id, "method": "tools/call", "params": params}


def _by_name(spans) -> dict:
    out: dict = {}
    for s in spans:
        out.setdefault(s.name, []).append(s)
    return out


def _all_attribute_values(spans) -> str:
    return json.dumps([dict(s.attributes or {}) for s in spans], default=str)


# ── Span tree for a tools/call ────────────────────────────────────────────────


class TestToolsCallSpans:
    @pytest.mark.asyncio
    async def test_server_span_name_attributes_and_meta_parent(self, authed_client, span_exporter):
        client, _, agent = authed_client
        with _pipeline(agent):
            resp = await client.post(
                MCP_URL,
                json=_tools_call(meta={"traceparent": META_TRACEPARENT}),
                headers={"traceparent": HTTP_TRACEPARENT, "MCP-Protocol-Version": "2025-06-18"},
            )
        assert resp.status_code == 200

        spans = _by_name(span_exporter.get_finished_spans())
        (server,) = spans["tools/call github__create_issue"]
        assert server.kind == SpanKind.SERVER
        attrs = dict(server.attributes)
        assert attrs["mcp.method.name"] == "tools/call"
        assert attrs["gen_ai.tool.name"] == "github__create_issue"
        assert attrs["gen_ai.operation.name"] == "execute_tool"
        assert attrs["jsonrpc.request.id"] == "7"
        assert attrs["mcp.protocol.version"] == "2025-06-18"
        assert attrs["network.transport"] == "tcp"
        assert attrs["arbiter.cache_hit"] is False
        assert "error.type" not in attrs

        # Parent = client span from params._meta (not the HTTP header).
        assert server.parent is not None and server.parent.is_remote
        assert format(server.parent.span_id, "016x") == CLIENT_SPAN_ID
        assert format(server.context.trace_id, "032x") == CLIENT_TRACE_ID
        # HTTP transport context is recorded as a link.
        assert len(server.links) == 1
        assert format(server.links[0].context.span_id, "016x") == HTTP_SPAN_ID

        # OTel trace id is surfaced next to the Arbiter session/event ids.
        assert resp.json()["result"]["_meta"]["arbiter"]["trace_id"] == CLIENT_TRACE_ID

    @pytest.mark.asyncio
    async def test_pipeline_child_spans_and_upstream_client_span(
        self, authed_client, span_exporter
    ):
        client, _, agent = authed_client
        with _pipeline(agent) as upstream:
            await client.post(MCP_URL, json=_tools_call(meta={"traceparent": META_TRACEPARENT}))

        finished = span_exporter.get_finished_spans()
        spans = _by_name(finished)
        (server,) = spans["tools/call github__create_issue"]
        server_id = server.context.span_id

        for stage in (
            "arbiter.rbac.check",
            "arbiter.rate_limit",
            "arbiter.cache.lookup",
            "arbiter.quota.check",
        ):
            (s,) = spans[stage]
            assert s.parent.span_id == server_id, stage
            assert s.kind == SpanKind.INTERNAL
        assert spans["arbiter.rbac.check"][0].attributes["arbiter.rbac.permitted"] is True
        assert spans["arbiter.cache.lookup"][0].attributes["arbiter.cache_hit"] is False
        vault_targets = sorted(
            s.attributes["arbiter.vault.target"] for s in spans["arbiter.vault.inject"]
        )
        assert vault_targets == ["arguments", "server_headers"]
        assert all(s.parent.span_id == server_id for s in spans["arbiter.vault.inject"])

        (up,) = spans["tools/call create_issue"]
        assert up.kind == SpanKind.CLIENT
        assert up.parent.span_id == server_id
        ua = dict(up.attributes)
        assert ua["mcp.method.name"] == "tools/call"
        assert ua["gen_ai.tool.name"] == "create_issue"
        assert ua["gen_ai.operation.name"] == "execute_tool"
        assert ua["server.address"] == "mcp.example.com"
        assert ua["server.port"] == 8443
        assert "error.type" not in ua
        # The URL (path/query may carry tokens) is never recorded.
        assert "token=nope" not in _all_attribute_values(finished)

        # traceparent injected into the upstream tools/call _meta, parented on
        # the CLIENT span, in the client's trace.
        (body,) = upstream.bodies
        tp = body["params"]["_meta"]["traceparent"]
        _, trace_id, span_id, _ = tp.split("-")
        assert trace_id == CLIENT_TRACE_ID
        assert span_id == format(up.context.span_id, "016x")
        assert body["params"]["name"] == "create_issue"

    @pytest.mark.asyncio
    async def test_header_traceparent_is_parent_when_meta_has_none(
        self, authed_client, span_exporter
    ):
        client, _, agent = authed_client
        with _pipeline(agent):
            await client.post(
                MCP_URL, json=_tools_call(), headers={"traceparent": HTTP_TRACEPARENT}
            )
        (server,) = _by_name(span_exporter.get_finished_spans())["tools/call github__create_issue"]
        assert format(server.parent.span_id, "016x") == HTTP_SPAN_ID
        assert format(server.context.trace_id, "032x") == HTTP_TRACE_ID
        assert len(server.links) == 0

    @pytest.mark.asyncio
    async def test_no_inbound_context_starts_new_root_trace(self, authed_client, span_exporter):
        client, _, agent = authed_client
        with _pipeline(agent):
            await client.post(MCP_URL, json=_tools_call())
        (server,) = _by_name(span_exporter.get_finished_spans())["tools/call github__create_issue"]
        assert server.parent is None

    @pytest.mark.asyncio
    async def test_rest_proxy_gets_server_span_with_stage_children(
        self, authed_client, span_exporter
    ):
        client, _, agent = authed_client
        with _pipeline(agent) as upstream:
            resp = await client.post(
                "/api/v1/proxy/tool-call",
                json={"server_name": "github", "tool_name": "create_issue", "params": {}},
                headers={"traceparent": HTTP_TRACEPARENT},
            )
        assert resp.status_code == 200
        spans = _by_name(span_exporter.get_finished_spans())
        (server,) = spans["execute_tool github__create_issue"]
        assert server.kind == SpanKind.SERVER
        assert server.attributes["gen_ai.operation.name"] == "execute_tool"
        assert format(server.parent.span_id, "016x") == HTTP_SPAN_ID
        assert spans["arbiter.rbac.check"][0].parent.span_id == server.context.span_id
        (up,) = spans["tools/call create_issue"]
        assert up.parent.span_id == server.context.span_id
        assert upstream.bodies[0]["params"]["_meta"]["traceparent"].split("-")[1] == HTTP_TRACE_ID


class TestErrorsAndCache:
    @pytest.mark.asyncio
    async def test_rbac_denial_sets_tool_error(self, authed_client, span_exporter):
        client, _, agent = authed_client
        with _pipeline(agent, permitted=False) as upstream:
            resp = await client.post(MCP_URL, json=_tools_call())
        assert resp.json()["result"]["isError"] is True
        spans = _by_name(span_exporter.get_finished_spans())
        server = spans["tools/call github__create_issue"][0]
        assert server.attributes["error.type"] == "tool_error"
        assert server.status.status_code == trace.StatusCode.ERROR
        assert spans["arbiter.rbac.check"][0].attributes["arbiter.rbac.permitted"] is False
        assert "tools/call create_issue" not in spans
        assert upstream.bodies == []

    @pytest.mark.asyncio
    async def test_upstream_jsonrpc_error_sets_error_type(self, authed_client, span_exporter):
        client, _, agent = authed_client
        upstream_err = {"jsonrpc": "2.0", "id": "x", "error": {"code": -32602, "message": "bad"}}
        with _pipeline(agent, upstream_json=upstream_err):
            await client.post(MCP_URL, json=_tools_call())
        (up,) = _by_name(span_exporter.get_finished_spans())["tools/call create_issue"]
        assert up.attributes["error.type"] == "-32602"
        assert up.attributes["rpc.response.status_code"] == "-32602"
        assert up.status.status_code == trace.StatusCode.ERROR

    @pytest.mark.asyncio
    async def test_upstream_iserror_result_sets_tool_error(self, authed_client, span_exporter):
        client, _, agent = authed_client
        tool_err = {"jsonrpc": "2.0", "id": "x", "result": {"content": [], "isError": True}}
        with _pipeline(agent, upstream_json=tool_err):
            await client.post(MCP_URL, json=_tools_call())
        spans = _by_name(span_exporter.get_finished_spans())
        assert spans["tools/call create_issue"][0].attributes["error.type"] == "tool_error"
        assert spans["tools/call github__create_issue"][0].attributes["error.type"] == "tool_error"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_upstream_span(self, authed_client, span_exporter):
        client, _, agent = authed_client
        with _pipeline(agent, cached={"content": [{"type": "text", "text": "cached"}]}) as up:
            await client.post(MCP_URL, json=_tools_call())
        spans = _by_name(span_exporter.get_finished_spans())
        assert spans["arbiter.cache.lookup"][0].attributes["arbiter.cache_hit"] is True
        assert spans["tools/call github__create_issue"][0].attributes["arbiter.cache_hit"] is True
        assert "tools/call create_issue" not in spans
        assert "arbiter.quota.check" not in spans
        assert up.bodies == []

    @pytest.mark.asyncio
    async def test_non_tool_methods_get_method_only_span_name(self, authed_client, span_exporter):
        client, _, _ = authed_client
        await client.post(MCP_URL, json={"jsonrpc": "2.0", "id": "p1", "method": "ping"})
        await client.post(MCP_URL, json={"jsonrpc": "2.0", "id": 2, "method": "nope"})
        spans = _by_name(span_exporter.get_finished_spans())
        assert spans["ping"][0].kind == SpanKind.SERVER
        assert spans["ping"][0].attributes["jsonrpc.request.id"] == "p1"
        assert "gen_ai.operation.name" not in spans["ping"][0].attributes
        assert spans["nope"][0].attributes["error.type"] == "-32601"
        assert spans["nope"][0].attributes["rpc.response.status_code"] == "-32601"


# ── Content + secrets ─────────────────────────────────────────────────────────


class TestContentCapture:
    @pytest.mark.asyncio
    async def test_arguments_and_results_not_recorded_by_default(
        self, authed_client, span_exporter
    ):
        client, _, agent = authed_client
        with _pipeline(agent) as upstream:
            await client.post(
                MCP_URL, json=_tools_call(arguments={"title": "private", "token": "{{GH_TOKEN}}"})
            )
        finished = span_exporter.get_finished_spans()
        dump = _all_attribute_values(finished)
        assert "gen_ai.tool.call.arguments" not in dump
        assert "gen_ai.tool.call.result" not in dump
        assert "private" not in dump
        assert SECRET_VALUE not in dump
        # Sanity: the secret really was injected upstream, just not traced.
        assert upstream.bodies[0]["params"]["arguments"]["token"] == SECRET_VALUE

    @pytest.mark.asyncio
    async def test_opt_in_capture_records_raw_arguments_never_secrets(self, authed_client):
        _reset_otel_globals()
        exporter = InMemorySpanExporter()
        telemetry.configure_telemetry(
            otel_enabled=True, capture_tool_content=True, span_exporter=exporter
        )
        try:
            client, _, agent = authed_client
            with _pipeline(agent):
                await client.post(
                    MCP_URL, json=_tools_call(arguments={"token": "{{GH_TOKEN}}", "title": "t"})
                )
            finished = exporter.get_finished_spans()
            (server,) = _by_name(finished)["tools/call github__create_issue"]
            args = json.loads(server.attributes["gen_ai.tool.call.arguments"])
            assert args == {"token": "{{GH_TOKEN}}", "title": "t"}
            assert json.loads(server.attributes["gen_ai.tool.call.result"]) == [
                {"type": "text", "text": "ok"}
            ]
            assert SECRET_VALUE not in _all_attribute_values(finished)
        finally:
            telemetry.shutdown_telemetry()
            _reset_otel_globals()


# ── Session trace id ──────────────────────────────────────────────────────────


class TestSessionTraceId:
    @pytest.mark.asyncio
    async def test_new_session_records_otel_trace_id(self, span_exporter):
        from app.services.proxy.proxy_service import ProxyService

        db = AsyncMock()
        db.add = MagicMock()
        service = ProxyService(db, AsyncMock())
        agent = MagicMock(id=uuid.uuid4(), org_id=uuid.uuid4())
        with telemetry.get_tracer().start_as_current_span("parent") as span:
            await service._ensure_session(agent=agent, session_id=None)
        session = db.add.call_args.args[0]
        assert session.metadata_ == {
            "otel_trace_id": format(span.get_span_context().trace_id, "032x")
        }

    @pytest.mark.asyncio
    async def test_new_session_metadata_empty_when_disabled(self, tracing_disabled):
        from app.services.proxy.proxy_service import ProxyService

        db = AsyncMock()
        db.add = MagicMock()
        service = ProxyService(db, AsyncMock())
        await service._ensure_session(agent=MagicMock(id=uuid.uuid4()), session_id=None)
        assert db.add.call_args.args[0].metadata_ == {}


# ── Disabled = no-op ──────────────────────────────────────────────────────────


class TestDisabled:
    def test_tracing_requested_switches(self, monkeypatch):
        for var in (
            "OTEL_SDK_DISABLED",
            "OTEL_TRACES_EXPORTER",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        ):
            monkeypatch.delenv(var, raising=False)
        # App flag off → off, even with an endpoint.
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
        assert telemetry.tracing_requested(False) is False
        # Flag on + endpoint → on.
        assert telemetry.tracing_requested(True) is True
        # Standard kill switches win.
        monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
        assert telemetry.tracing_requested(True) is False
        monkeypatch.delenv("OTEL_SDK_DISABLED")
        monkeypatch.setenv("OTEL_TRACES_EXPORTER", "none")
        assert telemetry.tracing_requested(True) is False
        monkeypatch.delenv("OTEL_TRACES_EXPORTER")
        # No exporter endpoint configured → off.
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        assert telemetry.tracing_requested(True) is False

    def test_configure_without_endpoint_installs_nothing(self, tracing_disabled, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        assert telemetry.configure_telemetry(otel_enabled=True) is False
        assert telemetry.is_enabled() is False
        assert not isinstance(trace.get_tracer_provider(), TracerProvider)

    @pytest.mark.asyncio
    async def test_tools_call_is_noop_when_disabled(self, authed_client, tracing_disabled):
        client, _, agent = authed_client
        with _pipeline(agent) as upstream:
            resp = await client.post(
                MCP_URL,
                json=_tools_call(meta={"traceparent": META_TRACEPARENT}),
                headers={"traceparent": HTTP_TRACEPARENT},
            )
        assert resp.status_code == 200
        # Wire format unchanged: nothing injected upstream, no trace id surfaced.
        (body,) = upstream.bodies
        assert "_meta" not in body["params"]
        assert "trace_id" not in resp.json()["result"]["_meta"]["arbiter"]
        assert not isinstance(trace.get_tracer_provider(), TracerProvider)
        assert telemetry.current_trace_id_hex() is None
