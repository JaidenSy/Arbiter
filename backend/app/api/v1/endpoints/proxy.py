"""
Arbiter API endpoints: Proxy (Tool Call Gateway).

This is the primary endpoint that agents call.  Every MCP tool invocation
passes through here, triggering the full pipeline:

    Auth → RBAC → Cache → Vault injection → MCP forward → Cache store → Audit log

Routes:
    POST   /proxy/tool-call   : invoke a tool through the gateway
    POST   /proxy/tools-list  : retrieve filtered tools list (RBAC-filtered)
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
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
        description="Calling session UUID: links this call into a multi-hop agent chain.",
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

    # Resolve server once (org-scoped): pass to filter_tools_list to avoid second DB round-trip.
    mcp_server = await service.resolve_server(body.server_name, agent.org_id)

    tools = await service.fetch_tools_list(mcp_server)

    filtered_tools = await service.filter_tools_list(
        agent=agent,
        server_name=body.server_name,
        tools=tools,
        mcp_server=mcp_server,
    )

    return ToolsListResponse(server_name=body.server_name, tools=filtered_tools)


class SessionBudgetResponse(BaseModel):
    """Response body for GET /proxy/session-budget."""

    session_id: str
    limit: int
    used: int
    remaining: int


@router.get(
    "/session-budget",
    response_model=SessionBudgetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get remaining tool-call budget for a session",
    dependencies=[Depends(require_org_verified)],
)
async def get_session_budget(
    session_id: str = Query(..., description="Session UUID to check budget for"),
    redis: object = Depends(get_redis),
    agent: Agent = Depends(get_current_agent),
) -> SessionBudgetResponse:
    """
    Return how many tool calls remain in the current session's budget.

    Returns 404 if the agent has no per-session budget configured.
    The counter resets after 24 hours (matching the session budget TTL).
    """
    if agent.max_calls_per_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This agent has no per-session budget configured",
        )
    budget_key = f"session_budget:{session_id}"
    raw = await redis.get(budget_key)
    used = int(raw) if raw is not None else 0
    remaining = max(0, agent.max_calls_per_session - used)
    return SessionBudgetResponse(
        session_id=session_id,
        limit=agent.max_calls_per_session,
        used=used,
        remaining=remaining,
    )
