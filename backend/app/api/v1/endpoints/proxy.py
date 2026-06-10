"""
Arbiter — API endpoints: Proxy (Tool Call Gateway).

This is the primary endpoint that agents call.  Every MCP tool invocation
passes through here, triggering the full pipeline:

    Auth → RBAC → Cache → Vault injection → MCP forward → Cache store → Audit log

Routes:
    POST   /proxy/tool-call    — invoke a tool through the gateway
    POST   /proxy/tools-list   — retrieve filtered tools list (RBAC-filtered)
"""

from __future__ import annotations

import json
import uuid as _uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_db, get_redis, require_org_verified
from app.db.models.agent import Agent
from app.schemas.proxy import ToolCallRequest, ToolCallResponse
from app.services.proxy.proxy_service import ProxyService

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.post(
    "/tool-call",
    response_model=ToolCallResponse,
    status_code=status.HTTP_200_OK,
    summary="Invoke an MCP tool through the Arbiter gateway",
    dependencies=[Depends(require_org_verified)],
)
async def tool_call(
    body: ToolCallRequest,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
    agent: Agent = Depends(get_current_agent),
    x_arbiter_parent_session_id: str | None = Header(
        None,
        alias="X-Arbiter-Parent-Session-Id",
        description="Calling session UUID — links this call into a multi-hop agent chain.",
    ),
) -> ToolCallResponse:
    """
    The central gateway endpoint for all MCP tool calls.

    Multi-hop tracing: pass X-Arbiter-Parent-Session-Id header (or
    body.parent_session_id) to link a child agent's session back to the
    originating session.  All sessions in the chain share a trace_id.
    """
    # Header takes precedence over body field; silently ignore malformed UUIDs.
    if x_arbiter_parent_session_id and body.parent_session_id is None:
        try:
            body = body.model_copy(
                update={"parent_session_id": _uuid.UUID(x_arbiter_parent_session_id)}
            )
        except ValueError:
            pass

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
    dependencies=[Depends(require_org_verified)],
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
    """
    service = ProxyService(db=db, redis=redis)

    # Resolve server once (org-scoped) — pass to filter_tools_list to avoid second DB round-trip.
    mcp_server = await service.resolve_server(body.server_name, agent.org_id)

    # Resolve vault-referenced auth headers so protected servers receive credentials.
    resolved_headers = await service.resolve_server_headers(mcp_server)
    request_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        **resolved_headers,
    }

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
                headers=request_headers,
            )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(f"MCP server {body.server_name!r} returned HTTP {resp.status_code}"),
            )
        if "text/event-stream" in resp.headers.get("content-type", ""):
            json_body: dict = {}
            for line in resp.text.splitlines():
                if line.startswith("data: "):
                    try:
                        candidate = json.loads(line[6:])
                        if "result" in candidate or "error" in candidate:
                            json_body = candidate
                    except json.JSONDecodeError:
                        pass
        else:
            json_body = resp.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MCP server communication error: {exc}",
        ) from exc

    tools: list[dict] = []
    if "result" in json_body and "tools" in json_body["result"]:
        tools = json_body["result"]["tools"]

    filtered_tools = await service.filter_tools_list(
        agent=agent,
        server_name=body.server_name,
        tools=tools,
        mcp_server=mcp_server,
    )

    return ToolsListResponse(server_name=body.server_name, tools=filtered_tools)
