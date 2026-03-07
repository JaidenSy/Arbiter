"""
NexusAI — API endpoints: Proxy (Tool Call Gateway).

This is the primary endpoint that agents call.  Every MCP tool invocation
passes through here, triggering the full pipeline:

    Auth → RBAC → Cache → Vault injection → MCP forward → Cache store → Audit log

Routes:
    POST   /proxy/tool-call   — invoke a tool through the gateway
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
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
            d. HTTP POST to the target MCP server
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
    # TODO: service = ProxyService(db=db, redis=redis)
    # TODO: return await service.forward_tool_call(request=body, agent=agent)
    raise NotImplementedError
