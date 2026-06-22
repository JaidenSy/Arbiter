# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
Arbiter Native MCP endpoint (Streamable HTTP transport).

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

JSON-RPC methods handled:
    initialize               : handshake; assigns an Mcp-Session-Id that maps
                                1:1 to an Arbiter audit Session
    notifications/*          : acknowledged with HTTP 202, no body
    ping                     : liveness check
    tools/list               : aggregated + RBAC-filtered + namespaced
    tools/call               : routed through ProxyService.forward_tool_call

Transport notes:
    - Responses are always application/json (single message). We do not open
      server-initiated SSE streams, so GET /mcp returns 405 per spec.
    - JSON-RPC batch arrays are rejected (removed from the MCP spec in
      2025-06-18).
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
from app.services.plan.plan_limits import QuotaExceededError, SessionBudgetExceededError
from app.services.proxy.proxy_service import ProxyService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])

# Protocol versions this gateway can speak. If the client requests one of
# these we echo it back; otherwise we answer with the latest we support and
# let the client decide (per MCP version negotiation rules).
_SUPPORTED_PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18"}
_LATEST_PROTOCOL_VERSION = "2025-06-18"

_SERVER_INFO = {"name": "arbiter-gateway", "version": "0.4.0"}

# Separator between server name and tool name in aggregated tool names.
# Split on the FIRST occurrence: MCPServerCreate rejects "__" in server
# names so the split is unambiguous; tool names may contain "__".
_TOOL_SEPARATOR = "__"

# Aggregated tools/list hits every upstream server in the org; MCP clients
# call it on every connect. Cached per-agent in Redis so reconnect storms
# don't fan out upstream. 60 s is short enough that permission changes
# propagate quickly.
_TOOLS_LIST_CACHE_TTL = 60

# JSON-RPC 2.0 error codes (spec) + -32000 for gateway/server errors.
_PARSE_ERROR = -32700
_INVALID_REQUEST = -32600
_METHOD_NOT_FOUND = -32601
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603
_SERVER_ERROR = -32000


def _rpc_error(req_id: Any, code: int, message: str, data: dict | None = None) -> dict:
    """Build a JSON-RPC 2.0 error response object."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": error}


def _rpc_result(req_id: Any, result: dict) -> dict:
    """Build a JSON-RPC 2.0 success response object."""
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _tool_error_result(req_id: Any, message: str) -> dict:
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


def _session_id_from_header(request: Request) -> _uuid.UUID | None:
    """Parse the Mcp-Session-Id header into a UUID, or None if absent/malformed."""
    raw = request.headers.get("Mcp-Session-Id")
    if not raw:
        return None
    try:
        return _uuid.UUID(raw)
    except ValueError:
        return None


@router.post(
    "/mcp",
    summary="Native MCP endpoint (Streamable HTTP): Bearer API key auth",
    dependencies=[Depends(require_org_verified)],
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


async def _handle_mcp_request(
    request: Request,
    agent: Agent,
    db: AsyncSession,
    redis: Any,
) -> Response:
    """Parse one JSON-RPC message and dispatch it. Returns the HTTP response."""
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
    if not isinstance(body, dict) or "method" not in body:
        return JSONResponse(
            _rpc_error(None, _INVALID_REQUEST, "Invalid Request: missing 'method'"),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    method: str = body["method"]
    req_id = body.get("id")
    params: dict[str, Any] = body.get("params") or {}

    # Per JSON-RPC 2.0, a message without an id is a notification: acknowledge
    # with 202 and no body. An id-bearing "notifications/*" message is a
    # malformed request and falls through to method-not-found below.
    if req_id is None:
        return Response(status_code=status.HTTP_202_ACCEPTED)

    if method == "ping":
        return JSONResponse(_rpc_result(req_id, {}))

    try:
        service = ProxyService(db=db, redis=redis)
        if method == "initialize":
            return await _handle_initialize(req_id, params, agent, service)
        if method == "tools/list":
            return await _handle_tools_list(req_id, agent, db, redis, service)
        if method == "tools/call":
            mcp_session_id = _session_id_from_header(request)
            return await _handle_tools_call(req_id, params, agent, service, mcp_session_id)
    except HTTPException:
        raise
    except Exception:
        # Never leak a bare HTTP 500 to an MCP client: surface a JSON-RPC
        # internal error so the client can show something actionable.
        logger.exception("mcp: unhandled error processing %r", method)
        return JSONResponse(_rpc_error(req_id, _INTERNAL_ERROR, "Internal error"))

    return JSONResponse(_rpc_error(req_id, _METHOD_NOT_FOUND, f"Method not found: {method!r}"))


async def _handle_initialize(
    req_id: Any,
    params: dict[str, Any],
    agent: Agent,
    service: ProxyService,
) -> JSONResponse:
    """
    MCP initialize handshake.

    Creates an Arbiter audit Session and returns its UUID as the
    Mcp-Session-Id header, so every subsequent tools/call from this client
    connection lands in one session trace.
    """
    requested = params.get("protocolVersion")
    protocol_version = (
        requested if requested in _SUPPORTED_PROTOCOL_VERSIONS else _LATEST_PROTOCOL_VERSION
    )

    session = await service.create_session(agent)

    result = {
        "protocolVersion": protocol_version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": _SERVER_INFO,
        "instructions": (
            "Arbiter MCP gateway. Tools are aggregated from your org's MCP "
            "servers and namespaced as <server>__<tool>. Calls are subject to "
            "your agent's RBAC permissions, rate limits, and quotas."
        ),
    }
    return JSONResponse(
        _rpc_result(req_id, result),
        headers={"Mcp-Session-Id": str(session.id)},
    )


async def _handle_tools_list(
    req_id: Any,
    agent: Agent,
    db: AsyncSession,
    redis: Any,
    service: ProxyService,
) -> JSONResponse:
    """
    Aggregate tools/list across all active MCP servers in the agent's org.

    Each server's list is RBAC-filtered for this agent, then namespaced.
    A server that is unreachable is skipped (logged) rather than failing the
    whole listing. Results are cached per-agent in Redis.
    """
    cache_key = f"mcp_tools_list:{agent.id}"
    try:
        cached = await redis.get(cache_key)
        if cached is not None:
            if isinstance(cached, bytes):
                cached = cached.decode()
            return JSONResponse(_rpc_result(req_id, {"tools": json.loads(cached)}))
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
    aggregated: list[dict] = []
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

    try:
        await redis.setex(cache_key, _TOOLS_LIST_CACHE_TTL, json.dumps(aggregated))
    except Exception as exc:
        logger.warning("mcp: tools/list cache write failed: %s", exc)

    return JSONResponse(_rpc_result(req_id, {"tools": aggregated}))


async def _handle_tools_call(
    req_id: Any,
    params: dict[str, Any],
    agent: Agent,
    service: ProxyService,
    mcp_session_id: _uuid.UUID | None,
) -> JSONResponse:
    """
    Route a namespaced tools/call through the full gateway pipeline.

    Gateway-side denials (RBAC 403, rate-limit 429, scope violation, quota
    exceeded, session budget exceeded) are returned as spec-compliant MCP tool
    errors: ``{"result": {"content": [...], "isError": true}}``.  This is the
    correct MCP representation for tool-level errors: JSON-RPC protocol errors
    (-32xxx) are reserved for transport/envelope problems only.

    Upstream 502/504 errors from the MCP server itself still surface as
    JSON-RPC -32000 errors because they represent a proxy failure, not a
    meaningful tool result.
    """
    name = params.get("name") or ""
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return JSONResponse(
            _rpc_error(
                req_id,
                _INVALID_PARAMS,
                f"'arguments' must be an object, got {type(arguments).__name__}",
            )
        )

    if _TOOL_SEPARATOR not in name:
        return JSONResponse(
            _rpc_error(
                req_id,
                _INVALID_PARAMS,
                (
                    f"Tool name {name!r} is not namespaced. Use "
                    f"'<server>{_TOOL_SEPARATOR}<tool>' as returned by tools/list."
                ),
            )
        )

    server_name, tool_name = name.split(_TOOL_SEPARATOR, 1)
    if not server_name or not tool_name:
        return JSONResponse(
            _rpc_error(
                req_id,
                _INVALID_PARAMS,
                f"Tool name {name!r} is malformed: expected '<server>{_TOOL_SEPARATOR}<tool>'.",
            )
        )
    tool_request = ToolCallRequest(
        server_name=server_name,
        tool_name=tool_name,
        params=arguments,
        session_id=mcp_session_id,
    )

    try:
        proxied = await service.forward_tool_call(request=tool_request, agent=agent)
    except HTTPException as exc:
        # RBAC denials (403), rate-limit rejections (429), scope violations
        # (403), and upstream 502/404 are all gateway-side tool errors.
        # Return isError: true per the MCP spec rather than a protocol error.
        detail = exc.detail if isinstance(exc.detail, str) else json.dumps(exc.detail)
        return JSONResponse(_tool_error_result(req_id, detail))
    except QuotaExceededError as exc:
        return JSONResponse(
            _tool_error_result(
                req_id,
                f"Monthly tool-call quota exceeded ({exc.used}/{exc.limit}); resets {exc.resets_at}",
            )
        )
    except SessionBudgetExceededError as exc:
        return JSONResponse(
            _tool_error_result(
                req_id,
                f"Per-session tool-call budget exceeded ({exc.used}/{exc.limit})",
            )
        )

    # proxied.result is the upstream's JSON-RPC `result` for tools/call,
    # already MCP-shaped ({content: [...], isError: ...}). Pass it through and
    # attach gateway observability in _meta (spec-reserved extension point).
    result = dict(proxied.result) if isinstance(proxied.result, dict) else {"content": []}
    meta = result.get("_meta") or {}
    meta["arbiter"] = {
        "session_id": str(proxied.session_id),
        "event_id": str(proxied.event_id),
        "cache_hit": proxied.cache_hit,
        "duration_ms": proxied.duration_ms,
    }
    result["_meta"] = meta

    return JSONResponse(
        _rpc_result(req_id, result),
        headers={"Mcp-Session-Id": str(proxied.session_id)},
    )
