"""
Arbiter API endpoints: Proxy (Tool Call Gateway).

This is the primary endpoint that agents call.  Every MCP tool invocation
passes through here, triggering the full pipeline:

    Auth → RBAC → Cache → Vault injection → MCP forward → Cache store → Audit log

Routes:
    POST   /proxy/tool-call   : invoke a tool through the gateway
    POST   /proxy/tools-list  : list tools on a server (all advertised; RBAC enforced at call time)
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from opentelemetry.trace import SpanKind
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_db, get_redis, require_org_verified
from app.core.telemetry import extract_mcp_context, get_tracer
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
    request: Request,
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
    # REST entry point gets its own SERVER span (parented on an inbound HTTP
    # traceparent, if any) so the pipeline-stage spans share one trace.
    tool = f"{body.server_name}__{body.tool_name}"
    parent_ctx, _ = extract_mcp_context(None, request.headers)
    with get_tracer().start_as_current_span(
        f"execute_tool {tool}",
        context=parent_ctx,
        kind=SpanKind.SERVER,
        attributes={"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": tool},
    ) as span:
        try:
            response = await service.forward_tool_call(request=body, agent=agent)
        except HTTPException as exc:
            span.set_attribute("error.type", str(exc.status_code))
            raise
        except Exception as exc:
            span.set_attribute("error.type", type(exc).__qualname__)
            raise
        span.set_attribute("arbiter.cache_hit", response.cache_hit)
        return response


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
    summary="List tools available on an MCP server",
    dependencies=[Depends(require_org_verified)],
)
async def tools_list(
    body: ToolsListRequest,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
    agent: Agent = Depends(get_current_agent),
) -> ToolsListResponse:
    """
    Retrieve the tools/list from an upstream MCP server.

    Every tool is advertised. RBAC is enforced at call time in
    forward_tool_call, so an unpermitted call is denied with a 403 and
    logged rather than the tool being hidden here.
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
