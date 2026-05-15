"""
NexVault — API endpoints: Tool Permissions.

Manages RBAC permission records that control which agents may call which
tools on which MCP servers.  Permissions are agent-scoped sub-resources.

Routes:
    POST   /agents/{agent_id}/permissions                  — grant a permission
    GET    /agents/{agent_id}/permissions                  — list permissions for an agent
    DELETE /agents/{agent_id}/permissions/{permission_id}  — revoke a permission
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.db.models.agent import Agent
from app.db.models.mcp_server import MCPServer
from app.db.models.user import User
from app.db.models.tool_permission import ToolPermission

router = APIRouter(prefix="/agents", tags=["tool-permissions"])


# ── Inline schemas ────────────────────────────────────────────────────────────


class ToolPermissionCreate(BaseModel):
    """Request body for granting a tool permission."""

    mcp_server_id: uuid.UUID
    tool_name: str = Field(
        ...,
        description="Tool name or '*' for all tools on this server",
    )
    cache_ttl_seconds: int | None = Field(
        None,
        ge=1,
        description="Override cache TTL for this tool in seconds. Null = global default.",
    )


class ToolPermissionResponse(BaseModel):
    """Response schema for a tool permission record."""

    id: uuid.UUID
    agent_id: uuid.UUID
    mcp_server_id: uuid.UUID
    tool_name: str
    granted_at: datetime
    granted_by: str | None
    cache_ttl_seconds: int | None

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/{agent_id}/permissions",
    response_model=ToolPermissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant a tool permission to an agent",
)
async def create_tool_permission(
    agent_id: uuid.UUID,
    body: ToolPermissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> ToolPermissionResponse:
    """
    Grant an agent permission to call a specific tool (or all tools) on an MCP server.

    Use tool_name='*' to grant access to all tools on the given server.

    Args:
        agent_id: UUID of the agent to grant permission to.
        body:     mcp_server_id and tool_name to permit.
        db:       Injected DB session.
        _current: Auth guard.

    Returns:
        ToolPermissionResponse: The created permission record.

    Raises:
        HTTPException 404: If agent_id or mcp_server_id does not exist.
        HTTPException 409: If this exact permission already exists.
    """
    # Verify agent exists and belongs to this org.
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.org_id == current_user.org_id, Agent.is_active.is_(True))
    )
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    # Verify MCP server exists and belongs to this org.
    server_result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == body.mcp_server_id,
            MCPServer.org_id == current_user.org_id,
            MCPServer.is_active.is_(True),
        )
    )
    if server_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP server {body.mcp_server_id} not found",
        )

    permission = ToolPermission(
        org_id=current_user.org_id,
        agent_id=agent_id,
        mcp_server_id=body.mcp_server_id,
        tool_name=body.tool_name,
        cache_ttl_seconds=body.cache_ttl_seconds,
    )
    db.add(permission)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Permission for agent {agent_id} on server {body.mcp_server_id} "
                f"tool {body.tool_name!r} already exists"
            ),
        ) from exc

    await db.refresh(permission)
    return ToolPermissionResponse.model_validate(permission)


@router.get(
    "/{agent_id}/permissions",
    response_model=list[ToolPermissionResponse],
    summary="List permissions for an agent",
)
async def list_tool_permissions(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ToolPermissionResponse]:
    """
    Return all tool permissions granted to a specific agent.

    Args:
        agent_id: UUID of the agent whose permissions to list.
        db:       Injected DB session.
        _current: Auth guard.

    Returns:
        list[ToolPermissionResponse]: All permissions for the agent.

    Raises:
        HTTPException 404: If the agent does not exist.
    """
    # Verify agent exists and belongs to this org.
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.org_id == current_user.org_id, Agent.is_active.is_(True))
    )
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found",
        )

    result = await db.execute(select(ToolPermission).where(ToolPermission.agent_id == agent_id))
    permissions = result.scalars().all()
    return [ToolPermissionResponse.model_validate(p) for p in permissions]


@router.delete(
    "/{agent_id}/permissions/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a tool permission",
)
async def delete_tool_permission(
    agent_id: uuid.UUID,
    permission_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Response:
    """
    Hard-delete a specific tool permission for an agent.

    Args:
        agent_id:      UUID of the agent that owns the permission.
        permission_id: UUID of the permission record to delete.
        db:            Injected DB session.
        _current:      Auth guard.

    Raises:
        HTTPException 404: If the permission does not exist or belongs to another agent.
    """
    result = await db.execute(
        select(ToolPermission).where(
            ToolPermission.id == permission_id,
            ToolPermission.agent_id == agent_id,
        )
    )
    permission = result.scalar_one_or_none()
    if permission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Permission {permission_id} not found for agent {agent_id}",
        )

    await db.delete(permission)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
