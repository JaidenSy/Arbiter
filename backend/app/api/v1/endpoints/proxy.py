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
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_db, get_redis
from app.db.models.agent import Agent
from app.schemas.proxy import ToolCallRequest, ToolCallResponse
from app.services.proxy.proxy_service import ProxyService

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.post(
    "/tool-call",
    response_model=ToolCallResponse,
    status_code=status.HTTP_200_OK,
    summary="Invoke an MCP tool through the NexusAI gateway",
)
async def tool_call(
    body: ToolCallRequest,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
    agent: Agent = Depends(get_current_agent),
) -> ToolCallResponse:
    """
    The central gateway endpoint for all MCP tool calls.

    This endpoint is the single entry point for all agent tool invocations.
    It delegates to ProxyService which implements the full pipeline.

    Request flow:
        1. get_current_agent() validates the Bearer API key.
        2. ProxyService.forward_tool_call() orchestrates:
            a. RBAC check (403 if denied)
            b. Semantic cache lookup (return early on hit)
            c. Vault secret injection into params
            d. HTTP POST to the target MCP server (JSON-RPC tools/call)
            e. Cache the response
            f. Persist SessionEvent audit record
        3. Return ToolCallResponse with result + metadata.

    Args:
        body:  Validated request body with server, tool, and params.
        db:    Injected async database session.
        redis: Injected async Redis client.
        agent: Authenticated agent (from Bearer token).

    Returns:
        ToolCallResponse: Tool result, cache metadata, session/event UUIDs.

    Raises:
        HTTPException 401: Missing or invalid API key.
        HTTPException 403: Agent lacks permission for this tool.
        HTTPException 404: MCP server not found or inactive.
        HTTPException 502: MCP server returned an error response.
    """
    service = ProxyService(db=db, redis=redis)
    return await service.forward_tool_call(request=body, agent=agent)


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

    # Resolve server (raises 404 if not found).
    mcp_server = await service._resolve_server(body.server_name)

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

    # Filter by RBAC — agent only sees permitted tools.
    filtered_tools = await service.filter_tools_list(
        agent=agent,
        server_name=body.server_name,
        tools=tools,
    )

    return ToolsListResponse(server_name=body.server_name, tools=filtered_tools)
