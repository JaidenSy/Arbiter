"""
NexusAI — API endpoints: Proxy (Tool Call Gateway).

This is the primary endpoint that agents call.  Every MCP tool invocation
passes through here, triggering the full pipeline:

    Auth → RBAC → Cache → Vault injection → MCP forward → Cache store → Audit log

Routes:
    POST   /proxy/tool-call    — invoke a tool through the gateway
    POST   /proxy/tools-list   — retrieve filtered tools list (RBAC-filtered)
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_db, get_redis
from app.db.models.agent import Agent
from app.schemas.proxy import ToolCallRequest, ToolCallResponse
from app.services.proxy.proxy_service import ProxyService

router = APIRouter(prefix="/proxy", tags=["proxy"])

_HTTP_TIMEOUT = httpx.Timeout(30.0)


@router.post(
    "/tool-call",
    response_model=None,
    summary="Invoke an MCP tool through the NexusAI gateway",
)
async def tool_call(
    body: ToolCallRequest,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
    agent: Agent = Depends(get_current_agent),
) -> ToolCallResponse | StreamingResponse:
    """
    The central gateway endpoint for all MCP tool calls.

    Opens a single upstream connection using ``httpx`` streaming mode,
    inspects the ``Content-Type`` response header, and branches:

    - ``application/json``    → buffers the full response body, runs cache
                                 write + audit, returns ``ToolCallResponse``.
    - ``text/event-stream``   → yields raw SSE bytes to the client via
                                 ``StreamingResponse``; audit is persisted on
                                 stream completion.

    The ``httpx.AsyncClient`` is kept alive for the duration of the SSE stream
    and closed by the generator's ``finally`` block.  This guarantees exactly
    one upstream HTTP call regardless of response type.

    Pre-flight (RBAC, cache lookup, vault injection) always runs before any
    bytes are forwarded to the client.

    Args:
        body:  Validated request body with server, tool, and params.
        db:    Injected async database session.
        redis: Injected async Redis client.
        agent: Authenticated agent (from Bearer token).

    Returns:
        ``ToolCallResponse`` (JSON) or ``StreamingResponse`` (SSE).

    Raises:
        HTTPException 401: Missing or invalid API key.
        HTTPException 403: Agent lacks permission for this tool.
        HTTPException 404: MCP server not found or inactive.
        HTTPException 502: MCP server returned an error response.
    """
    service = ProxyService(db=db, redis=redis)

    # ── Pre-flight (RBAC + cache + vault) ─────────────────────────────────────
    cache_hit_response, prepared = await service.prepare_tool_call(
        request=body, agent=agent
    )
    if cache_hit_response is not None:
        return cache_hit_response

    # ── Open upstream with streaming so we can inspect Content-Type first ────
    # The client is NOT used as a context manager here: for the SSE path the
    # generator must keep the client alive after this function returns.
    client = httpx.AsyncClient(timeout=_HTTP_TIMEOUT)
    try:
        resp = await client.send(
            client.build_request(
                "POST",
                prepared.mcp_server.base_url,
                json=prepared.jsonrpc_body,
                headers=prepared.outbound_headers,
            ),
            stream=True,
        )
    except httpx.TimeoutException as exc:
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MCP server {body.server_name!r} timed out after 30s",
        ) from exc
    except Exception as exc:
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MCP server communication error: {exc}",
        ) from exc

    content_type = resp.headers.get("content-type", "application/json")

    # ── SSE path ──────────────────────────────────────────────────────────────
    if "text/event-stream" in content_type:
        if resp.status_code >= 400:
            await resp.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"MCP server {body.server_name!r} returned HTTP {resp.status_code}",
            )

        async def _sse_gen():
            try:
                async for chunk in service.iter_sse_stream(
                    prepared=prepared,
                    tool_name=body.tool_name,
                    resp=resp,
                ):
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        return StreamingResponse(
            _sse_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── JSON (buffered) path ──────────────────────────────────────────────────
    try:
        await resp.aread()
    except Exception as exc:
        await resp.aclose()
        await client.aclose()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MCP server communication error: {exc}",
        ) from exc

    try:
        result = await service.finalize_json_call(
            prepared=prepared,
            tool_name=body.tool_name,
            http_resp=resp,
        )
    finally:
        await resp.aclose()
        await client.aclose()

    return result


class ToolsListRequest(BaseModel):
    """Request body for POST /proxy/tools-list."""

    server_name: str = Field(
        ...,
        description="Logical name of the MCP server to query for tools",
    )


class ToolsListResponse(BaseModel):
    """Response from POST /proxy/tools-list."""

    server_name: str
    tools: list[dict[str, Any]]


@router.post(
    "/tools-list",
    response_model=ToolsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List tools available on an MCP server (RBAC-filtered)",
)
async def tools_list(
    body: ToolsListRequest,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
    agent: Agent = Depends(get_current_agent),
) -> ToolsListResponse:
    """
    Retrieve and RBAC-filter the tools/list from an upstream MCP server.

    Calls the upstream server's tools/list endpoint and filters the result
    so the agent only sees tools they are permitted to call.  This prevents
    information leakage about tools the agent cannot access.

    Args:
        body:  Request body containing server_name.
        db:    Injected async database session.
        redis: Injected async Redis client.
        agent: Authenticated agent (from Bearer token).

    Returns:
        ToolsListResponse: List of permitted tools for this agent.

    Raises:
        HTTPException 401: Missing or invalid API key.
        HTTPException 404: MCP server not found or inactive.
        HTTPException 502: Upstream MCP server communication error.
    """
    service = ProxyService(db=db, redis=redis)

    # Resolve server once — pass to filter_tools_list to avoid second DB round-trip.
    mcp_server = await service.resolve_server(body.server_name)

    # Build JSON-RPC tools/list request.
    jsonrpc_body = {
        "jsonrpc": "2.0",
        "id": "tools-list",
        "method": "tools/list",
        "params": {},
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            resp = await client.post(
                mcp_server.base_url,
                json=jsonrpc_body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"MCP server {body.server_name!r} returned "
                    f"HTTP {resp.status_code}"
                ),
            )
        json_body = resp.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MCP server communication error: {exc}",
        ) from exc

    # Extract tool list from JSON-RPC response.
    tools: list[dict] = []
    if "result" in json_body and "tools" in json_body["result"]:
        tools = json_body["result"]["tools"]

    # Filter by RBAC — pass pre-resolved server to avoid second DB round-trip.
    filtered_tools = await service.filter_tools_list(
        agent=agent,
        server_name=body.server_name,
        tools=tools,
        mcp_server=mcp_server,
    )

    return ToolsListResponse(server_name=body.server_name, tools=filtered_tools)
