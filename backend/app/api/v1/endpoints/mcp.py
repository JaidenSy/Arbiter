# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
Arbiter Native MCP endpoint (Streamable HTTP transport, dual-era).

Exposes the gateway itself as a spec-compliant MCP server so any MCP client
(Claude Code, Claude Desktop, Cursor, VS Code, ...) can connect with a single
URL: no custom integration code.

The org's registered MCP servers are aggregated into one virtual server:
tool names are namespaced as ``{server_name}__{tool_name}``.  Every
``tools/call`` runs through the full ProxyService pipeline (RBAC, vault
injection, semantic cache, quota, budgets, audit log): identical to the
REST proxy.

Routes (mounted at the application root, NOT under /api/v1):
    POST   /mcp             : JSON-RPC 2.0 endpoint, Bearer nxai_... auth
    POST   /mcp/{api_key}   : key-in-URL variant for clients that cannot
                               set custom headers

Protocol eras (MCP 2026-07-28 "Versioning: Backward Compatibility"):

    Modern (2026-07-28): selected when the request carries
        ``params._meta["io.modelcontextprotocol/protocolVersion"]`` (or a
        modern ``MCP-Protocol-Version`` header, or the method is
        ``server/discover``). Served statelessly: no initialize, no
        Mcp-Session-Id. ``MCP-Protocol-Version``/``Mcp-Method``/``Mcp-Name``
        headers must match the body (-32020 HeaderMismatch, HTTP 400); an
        unsupported version gets -32022 UnsupportedProtocolVersion (HTTP 400).
        Every result carries ``resultType``; ``server/discover`` and
        ``tools/list`` carry ``ttlMs``/``cacheScope``.
        Methods: server/discover, tools/list, tools/call.

    Legacy (2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05): the
        initialize-based flow, unchanged in shape. ``initialize`` mints an
        Mcp-Session-Id that maps 1:1 to an Arbiter audit Session.
        Methods: initialize, ping, tools/list, tools/call; notifications/*
        acknowledged with 202.

Arbiter audit sessions in the modern era: protocol sessions no longer exist,
so modern clients group calls by passing an explicit Arbiter session handle,
either ``params._meta["dev.arbiterai/sessionId"]`` or the
``X-Arbiter-Session-Id`` header. The handle is a session UUID returned in
every tools/call result's ``_meta``. It is bound to the authenticated agent:
a handle belonging to another agent is ignored and a new session is created
(ProxyService._ensure_session), so a handle is never authentication.

Transport notes (both eras):
    - The Origin header is validated on every request; present-and-not-
      allowlisted -> 403 (settings.mcp_allowed_origins, falling back to
      cors_origins).
    - Responses are always application/json (single message). We do not open
      SSE streams, so GET/DELETE /mcp return 405.
    - JSON-RPC batch arrays are rejected (removed in MCP 2025-06-18).

The protocol plumbing (constants, header encoding, era detection) lives in
``app.services.mcp.protocol`` and mirrors the official SDK's names so the
dispatcher can later be swapped for ``mcp`` 2.x's MCPServer.
"""

from __future__ import annotations

import json
import logging
import uuid as _uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import (
    ensure_org_verified,
    get_current_agent,
    get_db,
    get_redis,
    require_org_verified,
    resolve_agent_by_api_key,
)
from app.db.models.agent import Agent
from app.db.models.mcp_server import MCPServer
from app.schemas.proxy import ToolCallRequest
from app.services.mcp import protocol as p
from app.services.plan.plan_limits import QuotaExceededError, SessionBudgetExceededError
from app.services.proxy.proxy_service import ProxyService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])

# Kept for backward compatibility with importers; the source of truth is
# app.services.mcp.protocol.
_SUPPORTED_PROTOCOL_VERSIONS = set(p.LEGACY_PROTOCOL_VERSIONS)
_LATEST_PROTOCOL_VERSION = p.LATEST_LEGACY_PROTOCOL_VERSION

_SERVER_INFO = {"name": "arbiter-gateway", "version": "0.5.0"}

_INSTRUCTIONS = (
    "Arbiter MCP gateway. Tools are aggregated from your org's MCP "
    "servers and namespaced as <server>__<tool>. Calls are subject to "
    "your agent's RBAC permissions, rate limits, and quotas."
)

# Separator between server name and tool name in aggregated tool names.
# Split on the FIRST occurrence: MCPServerCreate rejects "__" in server
# names so the split is unambiguous; tool names may contain "__".
_TOOL_SEPARATOR = "__"

# Aggregated tools/list hits every upstream server in the org; MCP clients
# call it on every connect. Cached in Redis so reconnect storms don't fan
# out upstream. The listing no longer depends on the agent's permissions
# (every tool is advertised; RBAC is enforced at call time), so the cache
# could be keyed per-org; it is currently keyed per-agent.
_TOOLS_LIST_CACHE_TTL = 60

# Modern-era caching hints. tools/list depends on the caller's org (and is
# behind agent auth), so it is "private". server/discover is identical for
# every caller, so shared intermediaries may cache it.
_TOOLS_LIST_TTL_MS = _TOOLS_LIST_CACHE_TTL * 1000
_DISCOVER_TTL_MS = 3_600_000

# Re-exported for older importers/tests.
_PARSE_ERROR = p.PARSE_ERROR
_INVALID_REQUEST = p.INVALID_REQUEST
_METHOD_NOT_FOUND = p.METHOD_NOT_FOUND
_INVALID_PARAMS = p.INVALID_PARAMS
_INTERNAL_ERROR = p.INTERNAL_ERROR
_SERVER_ERROR = p.SERVER_ERROR

_rpc_error = p.rpc_error
_rpc_result = p.rpc_result


def _tool_error_result(req_id: Any, message: str) -> dict[str, Any]:
    """
    Build a spec-compliant MCP tool error response.

    Per the MCP spec, tool-level errors (RBAC denials, rate-limit rejections,
    scope violations, quota exceeded) must be returned as a successful JSON-RPC
    result with ``isError: true`` rather than a JSON-RPC protocol error.  This
    lets MCP clients handle the denial gracefully at the tool layer instead of
    treating it as a transport failure.
    """
    return _rpc_result(
        req_id,
        {"content": [{"type": "text", "text": message}], "isError": True},
    )


def _parse_uuid(raw: Any) -> _uuid.UUID | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return _uuid.UUID(raw)
    except ValueError:
        return None


def _session_id_from_header(request: Request) -> _uuid.UUID | None:
    """Parse the Mcp-Session-Id header into a UUID, or None if absent/malformed."""
    return _parse_uuid(request.headers.get(p.HEADER_SESSION_ID))


def _modern_session_handle(request: Request, params: dict[str, Any]) -> _uuid.UUID | None:
    """Arbiter session handle for a modern request: _meta key first, then header."""
    meta = p.request_meta(params) or {}
    handle = _parse_uuid(meta.get(p.META_ARBITER_SESSION_ID))
    if handle is not None:
        return handle
    return _parse_uuid(request.headers.get(p.HEADER_ARBITER_SESSION_ID))


# ── Origin validation ─────────────────────────────────────────────────────────


def _origin_allowed(origin: str) -> bool:
    allowed = settings.mcp_allowed_origin_list
    if "*" in allowed:
        return True
    normalized = origin.rstrip("/")
    return any(normalized == a.rstrip("/") for a in allowed)


async def validate_origin(request: Request) -> None:
    """
    Streamable HTTP "Security & Endpoint": servers MUST validate Origin and
    respond 403 when it is present and invalid (DNS-rebinding defence).
    Runs before authentication so a hostile page can't probe auth state.
    """
    origin = request.headers.get("origin")
    if origin is None:
        return
    if not _origin_allowed(origin):
        logger.warning("mcp: rejected request from disallowed Origin %r", origin)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed")


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/mcp",
    summary="Native MCP endpoint (Streamable HTTP): Bearer API key auth",
    dependencies=[Depends(validate_origin), Depends(require_org_verified)],
)
async def mcp_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
    agent: Agent = Depends(get_current_agent),
) -> Response:
    """
    MCP Streamable HTTP endpoint. Authenticate with ``Authorization: Bearer nxai_...``.
    """
    return await _handle_mcp_request(request, agent, db, redis)


@router.post(
    "/mcp/{api_key}",
    summary="Native MCP endpoint: key-in-URL variant",
    include_in_schema=False,
    dependencies=[Depends(validate_origin)],
)
async def mcp_endpoint_keyed(
    api_key: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
) -> Response:
    """
    Same endpoint, but the agent API key is embedded in the path. For MCP
    clients that cannot send custom headers. Treat the full URL as a secret.
    """
    agent = await resolve_agent_by_api_key(api_key, db)
    await ensure_org_verified(agent, db, redis)
    return await _handle_mcp_request(request, agent, db, redis)


# ── Dispatch ──────────────────────────────────────────────────────────────────


async def _handle_mcp_request(
    request: Request,
    agent: Agent,
    db: AsyncSession,
    redis: Any,
) -> Response:
    """Parse one JSON-RPC message, pick the protocol era, and dispatch it."""
    try:
        body = json.loads(await request.body())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(
            _rpc_error(None, _PARSE_ERROR, "Parse error: request body is not valid JSON"),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(body, list):
        return JSONResponse(
            _rpc_error(
                None,
                _INVALID_REQUEST,
                "JSON-RPC batching is not supported (removed in MCP 2025-06-18)",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if not isinstance(body, dict) or not isinstance(body.get("method"), str):
        return JSONResponse(
            _rpc_error(None, _INVALID_REQUEST, "Invalid Request: missing 'method'"),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    method: str = body["method"]
    req_id = body.get("id")
    raw_params = body.get("params")
    if raw_params is not None and not isinstance(raw_params, dict):
        return JSONResponse(
            _rpc_error(req_id, _INVALID_PARAMS, "'params' must be an object"),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    params: dict[str, Any] = raw_params or {}

    # Per JSON-RPC 2.0, a message without an id is a notification: acknowledge
    # with 202 and no body. An id-bearing "notifications/*" message is a
    # malformed request and falls through to method-not-found below.
    if req_id is None:
        return Response(status_code=status.HTTP_202_ACCEPTED)

    header_version = request.headers.get(p.HEADER_PROTOCOL_VERSION)
    is_modern = (
        p.modern_protocol_version(params) is not None
        or p.is_modern_version(header_version)
        or method == "server/discover"
    )

    try:
        if is_modern:
            return await _handle_modern(request, method, req_id, params, agent, db, redis)
        return await _handle_legacy(
            request, method, req_id, params, header_version, agent, db, redis
        )
    except HTTPException:
        raise
    except Exception:
        # Never leak a bare HTTP 500 to an MCP client: surface a JSON-RPC
        # internal error so the client can show something actionable.
        logger.exception("mcp: unhandled error processing %r", method)
        return JSONResponse(_rpc_error(req_id, _INTERNAL_ERROR, "Internal error"))


# ── Legacy era (initialize-based) ─────────────────────────────────────────────


async def _handle_legacy(
    request: Request,
    method: str,
    req_id: Any,
    params: dict[str, Any],
    header_version: str | None,
    agent: Agent,
    db: AsyncSession,
    redis: Any,
) -> Response:
    """
    Serve an initialize-era request.

    ``MCP-Protocol-Version`` (2025-06-18+) is validated when present; absent
    is treated as 2025-03-26 per the spec's backward-compatibility allowance.
    """
    if header_version is not None and header_version not in p.LEGACY_PROTOCOL_VERSIONS:
        return JSONResponse(
            p.unsupported_version_error(req_id, header_version),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if method == "ping":
        return JSONResponse(_rpc_result(req_id, {}))

    service = ProxyService(db=db, redis=redis)
    if method == "initialize":
        return await _handle_initialize(req_id, params, agent, service)
    if method == "tools/list":
        tools = await _aggregate_tools(agent, db, redis, service)
        return JSONResponse(_rpc_result(req_id, {"tools": tools}))
    if method == "tools/call":
        payload, session_id = await _handle_tools_call(
            req_id, params, agent, service, _session_id_from_header(request)
        )
        headers = {p.HEADER_SESSION_ID: str(session_id)} if session_id else None
        return JSONResponse(payload, headers=headers)

    return JSONResponse(_rpc_error(req_id, _METHOD_NOT_FOUND, f"Method not found: {method!r}"))


async def _handle_initialize(
    req_id: Any,
    params: dict[str, Any],
    agent: Agent,
    service: ProxyService,
) -> JSONResponse:
    """
    MCP initialize handshake (legacy era).

    Creates an Arbiter audit Session and returns its UUID as the
    Mcp-Session-Id header, so every subsequent tools/call from this client
    connection lands in one session trace. Negotiates the client's version
    when we speak it, else answers with our newest legacy version and lets
    the client decide (legacy version-negotiation rules).
    """
    requested = params.get("protocolVersion")
    protocol_version = (
        requested
        if isinstance(requested, str) and requested in p.LEGACY_PROTOCOL_VERSIONS
        else p.LATEST_LEGACY_PROTOCOL_VERSION
    )

    session = await service.create_session(agent)

    result = {
        "protocolVersion": protocol_version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": _SERVER_INFO,
        "instructions": _INSTRUCTIONS,
    }
    return JSONResponse(
        _rpc_result(req_id, result),
        headers={p.HEADER_SESSION_ID: str(session.id)},
    )


# ── Modern era (2026-07-28, stateless) ────────────────────────────────────────


def _header_mismatch(req_id: Any, message: str) -> JSONResponse:
    return JSONResponse(
        _rpc_error(req_id, p.HEADER_MISMATCH, f"Header mismatch: {message}"),
        status_code=status.HTTP_400_BAD_REQUEST,
    )


def _validate_modern_request(
    request: Request, method: str, req_id: Any, params: dict[str, Any]
) -> JSONResponse | None:
    """
    Enforce the 2026-07-28 request contract. Returns an error response or None.

    Order: protocol-version header vs ``_meta`` (-32020 / -32602), version
    support (-32022), ``Mcp-Method`` / ``Mcp-Name`` vs body (-32020),
    required ``clientCapabilities`` (-32602). All are HTTP 400.
    """
    header_version = request.headers.get(p.HEADER_PROTOCOL_VERSION)
    meta = p.request_meta(params)
    meta_version = meta.get(p.META_PROTOCOL_VERSION) if meta is not None else None

    if meta_version is None:
        return JSONResponse(
            _rpc_error(
                req_id,
                _INVALID_PARAMS,
                f"Invalid params: missing params._meta[{p.META_PROTOCOL_VERSION!r}]",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    if header_version is None:
        return _header_mismatch(req_id, f"missing required {p.HEADER_PROTOCOL_VERSION} header")
    if header_version != meta_version:
        return _header_mismatch(
            req_id,
            f"{p.HEADER_PROTOCOL_VERSION} header value {header_version!r} does not match "
            f"body value {meta_version!r}",
        )
    if not p.is_modern_version(meta_version):
        return JSONResponse(
            p.unsupported_version_error(req_id, meta_version),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    header_method = request.headers.get(p.HEADER_METHOD)
    if header_method is None:
        return _header_mismatch(req_id, f"missing required {p.HEADER_METHOD} header")
    if header_method != method:
        return _header_mismatch(
            req_id,
            f"{p.HEADER_METHOD} header value {header_method!r} does not match "
            f"body value {method!r}",
        )

    name_field = p.NAMED_METHODS.get(method)
    if name_field is not None:
        raw_name = request.headers.get(p.HEADER_NAME)
        body_name = params.get(name_field)
        if raw_name is None:
            return _header_mismatch(req_id, f"missing required {p.HEADER_NAME} header")
        decoded = p.decode_header_value(raw_name)
        if decoded is None:
            return _header_mismatch(req_id, f"{p.HEADER_NAME} header contains invalid characters")
        if decoded != body_name:
            return _header_mismatch(
                req_id,
                f"{p.HEADER_NAME} header value {decoded!r} does not match body value {body_name!r}",
            )

    assert meta is not None
    if not isinstance(meta.get(p.META_CLIENT_CAPABILITIES), dict):
        return JSONResponse(
            _rpc_error(
                req_id,
                _INVALID_PARAMS,
                f"Invalid params: missing params._meta[{p.META_CLIENT_CAPABILITIES!r}]",
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return None


def _complete(result: dict[str, Any], **extra_meta: Any) -> dict[str, Any]:
    """Stamp a modern result: resultType + serverInfo in _meta."""
    out = dict(result)
    out.setdefault("resultType", p.RESULT_TYPE_COMPLETE)
    meta = dict(out.get("_meta") or {})
    meta[p.META_SERVER_INFO] = _SERVER_INFO
    meta.update(extra_meta)
    out["_meta"] = meta
    return out


async def _handle_modern(
    request: Request,
    method: str,
    req_id: Any,
    params: dict[str, Any],
    agent: Agent,
    db: AsyncSession,
    redis: Any,
) -> Response:
    """Serve a stateless 2026-07-28 request. Never mints or echoes Mcp-Session-Id."""
    error = _validate_modern_request(request, method, req_id, params)
    if error is not None:
        return error

    if method == "server/discover":
        result = {
            "supportedVersions": list(p.SUPPORTED_PROTOCOL_VERSIONS),
            "capabilities": {"tools": {}},
            "instructions": _INSTRUCTIONS,
            "ttlMs": _DISCOVER_TTL_MS,
            "cacheScope": p.CACHE_SCOPE_PUBLIC,
        }
        return JSONResponse(_rpc_result(req_id, _complete(result)))

    service = ProxyService(db=db, redis=redis)
    if method == "tools/list":
        tools = await _aggregate_tools(agent, db, redis, service)
        result = {
            "tools": tools,
            "ttlMs": _TOOLS_LIST_TTL_MS,
            "cacheScope": p.CACHE_SCOPE_PRIVATE,
        }
        return JSONResponse(_rpc_result(req_id, _complete(result)))

    if method == "tools/call":
        payload, session_id = await _handle_tools_call(
            req_id, params, agent, service, _modern_session_handle(request, params)
        )
        if "result" in payload:
            extra = {p.META_ARBITER_SESSION_ID: str(session_id)} if session_id else {}
            payload = _rpc_result(req_id, _complete(payload["result"], **extra))
        return JSONResponse(payload)

    # Spec: an unimplemented RPC method -> 404 with -32601 (distinguishes us
    # from a legacy HTTP+SSE server's bare 404). ping/initialize are legacy-only.
    return JSONResponse(
        _rpc_error(req_id, _METHOD_NOT_FOUND, f"Method not found: {method!r}"),
        status_code=status.HTTP_404_NOT_FOUND,
    )


# ── Shared method implementations ─────────────────────────────────────────────


async def _aggregate_tools(
    agent: Agent,
    db: AsyncSession,
    redis: Any,
    service: ProxyService,
) -> list[dict[str, Any]]:
    """
    Aggregate tools/list across all active MCP servers in the agent's org.

    Each server's list is RBAC-filtered for this agent, then namespaced.
    A server that is unreachable is skipped (logged) rather than failing the
    whole listing. Results are cached per-agent in Redis.

    The list is returned sorted by namespaced name: 2026-07-28 says servers
    SHOULD return tools in a deterministic order (it keeps downstream prompt
    caches warm), and it costs nothing for legacy clients.
    """
    cache_key = f"mcp_tools_list:{agent.id}"
    try:
        cached = await redis.get(cache_key)
        if cached is not None:
            if isinstance(cached, bytes):
                cached = cached.decode()
            return sorted(json.loads(cached), key=lambda t: str(t.get("name", "")))
    except Exception as exc:  # Redis down → fall through to live fetch
        logger.warning("mcp: tools/list cache read failed: %s", exc)

    result_servers = await db.execute(
        select(MCPServer).where(
            MCPServer.org_id == agent.org_id,
            MCPServer.is_active.is_(True),
        )
    )
    servers = list(result_servers.scalars().all())

    # Servers are fetched sequentially on purpose: ProxyService shares this
    # request's AsyncSession, and a SQLAlchemy async session must not be used
    # concurrently. Parallelizing needs a session per task: follow-up.
    aggregated: list[dict[str, Any]] = []
    for server in servers:
        # Any failure (unreachable upstream, RBAC lookup error) skips this one
        # server rather than failing the whole aggregated listing.
        try:
            raw_tools = await service.fetch_tools_list(server)
            tools = await service.filter_tools_list(
                agent=agent,
                server_name=server.name,
                tools=raw_tools,
                mcp_server=server,
            )
        except HTTPException as exc:
            logger.warning(
                "mcp: skipping server %r in aggregated tools/list: %s", server.name, exc.detail
            )
            continue
        except Exception as exc:
            logger.warning("mcp: skipping server %r in aggregated tools/list: %s", server.name, exc)
            continue
        for tool in tools:
            if not tool.get("name"):
                logger.warning(
                    "mcp: server %r returned a tool without a name: skipped", server.name
                )
                continue
            namespaced = dict(tool)
            namespaced["name"] = f"{server.name}{_TOOL_SEPARATOR}{tool['name']}"
            aggregated.append(namespaced)

    aggregated.sort(key=lambda t: str(t["name"]))

    try:
        await redis.setex(cache_key, _TOOLS_LIST_CACHE_TTL, json.dumps(aggregated))
    except Exception as exc:
        logger.warning("mcp: tools/list cache write failed: %s", exc)

    return aggregated


async def _handle_tools_call(
    req_id: Any,
    params: dict[str, Any],
    agent: Agent,
    service: ProxyService,
    session_id: _uuid.UUID | None,
) -> tuple[dict[str, Any], _uuid.UUID | None]:
    """
    Route a namespaced tools/call through the full gateway pipeline.

    Returns (JSON-RPC payload, audit session id or None). The caller decides
    how the session id travels back: the Mcp-Session-Id header (legacy) or
    ``_meta["dev.arbiterai/sessionId"]`` (modern).

    Gateway-side denials (RBAC 403, rate-limit 429, scope violation, quota
    exceeded, session budget exceeded) are returned as spec-compliant MCP tool
    errors: ``{"result": {"content": [...], "isError": true}}``.  This is the
    correct MCP representation for tool-level errors: JSON-RPC protocol errors
    (-32xxx) are reserved for transport/envelope problems only.
    """
    name = params.get("name") or ""
    arguments = params.get("arguments") or {}
    if not isinstance(name, str):
        return _rpc_error(req_id, _INVALID_PARAMS, "'name' must be a string"), None
    if not isinstance(arguments, dict):
        return (
            _rpc_error(
                req_id,
                _INVALID_PARAMS,
                f"'arguments' must be an object, got {type(arguments).__name__}",
            ),
            None,
        )

    if _TOOL_SEPARATOR not in name:
        return (
            _rpc_error(
                req_id,
                _INVALID_PARAMS,
                (
                    f"Tool name {name!r} is not namespaced. Use "
                    f"'<server>{_TOOL_SEPARATOR}<tool>' as returned by tools/list."
                ),
            ),
            None,
        )

    server_name, tool_name = name.split(_TOOL_SEPARATOR, 1)
    if not server_name or not tool_name:
        return (
            _rpc_error(
                req_id,
                _INVALID_PARAMS,
                f"Tool name {name!r} is malformed: expected '<server>{_TOOL_SEPARATOR}<tool>'.",
            ),
            None,
        )
    tool_request = ToolCallRequest(
        server_name=server_name,
        tool_name=tool_name,
        params=arguments,
        session_id=session_id,
    )

    try:
        proxied = await service.forward_tool_call(request=tool_request, agent=agent)
    except HTTPException as exc:
        # RBAC denials (403), rate-limit rejections (429), scope violations
        # (403), and upstream 502/404 are all gateway-side tool errors.
        # Return isError: true per the MCP spec rather than a protocol error.
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)
        return _tool_error_result(req_id, detail), None
    except QuotaExceededError as exc:
        return (
            _tool_error_result(
                req_id,
                f"Monthly tool-call quota exceeded ({exc.used}/{exc.limit}); resets {exc.resets_at}",
            ),
            None,
        )
    except SessionBudgetExceededError as exc:
        return (
            _tool_error_result(
                req_id,
                f"Per-session tool-call budget exceeded ({exc.used}/{exc.limit})",
            ),
            None,
        )

    # proxied.result is the upstream's JSON-RPC `result` for tools/call,
    # already MCP-shaped ({content: [...], isError: ...}). Pass it through and
    # attach gateway observability in _meta (spec-reserved extension point).
    result = dict(proxied.result) if isinstance(proxied.result, dict) else {"content": []}

    upstream_type = result.get("resultType")
    if upstream_type is not None and upstream_type != p.RESULT_TYPE_COMPLETE:
        # A modern upstream asked for client input (MRTR "input_required") or
        # returned a task. Relaying requestState/inputResponses through the
        # gateway is not implemented yet, so fail closed with a tool error
        # instead of handing the client a result shape it never negotiated.
        return (
            _tool_error_result(
                req_id,
                (
                    f"Upstream tool {name!r} returned resultType {upstream_type!r}, "
                    "which the Arbiter gateway does not relay yet."
                ),
            ),
            proxied.session_id,
        )

    meta = result.get("_meta") or {}
    meta["arbiter"] = {
        "session_id": str(proxied.session_id),
        "event_id": str(proxied.event_id),
        "cache_hit": proxied.cache_hit,
        "duration_ms": proxied.duration_ms,
    }
    result["_meta"] = meta

    return _rpc_result(req_id, result), proxied.session_id
