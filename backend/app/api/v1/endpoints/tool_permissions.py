"""
Arbiter — API endpoints: Tool Permissions.

Manages RBAC permission records that control which agents may call which
tools on which MCP servers.  Permissions are agent-scoped sub-resources.

Routes:
    POST   /agents/{agent_id}/permissions                  — grant a permission
    GET    /agents/{agent_id}/permissions                  — list permissions for an agent
    PATCH  /agents/{agent_id}/permissions/{permission_id}  — update rate limits
    DELETE /agents/{agent_id}/permissions/{permission_id}  — revoke a permission
    GET    /agents/{agent_id}/permissions/history          — audit log
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.schemas.pagination import Page
from app.db.models.agent import Agent
from app.db.models.mcp_server import MCPServer
from app.db.models.user import User
from app.db.models.tool_permission import ToolPermission
from app.db.models.tool_permission_event import ToolPermissionEvent

router = APIRouter(prefix="/agents", tags=["tool-permissions"])


# ── Inline schemas ────────────────────────────────────────────────────────────


class ToolPermissionCreate(BaseModel):
    """Request body for granting a tool permission."""

    mcp_server_id: uuid.UUID
    tool_name: str = Field(
        ...,
        description="Tool name or '*' for all tools on this server",
    )
    rate_limit_per_minute: int | None = Field(
        None,
        ge=1,
        description="Max calls per minute for this agent+tool. Null = unlimited.",
    )
    cache_ttl_seconds: int | None = Field(
        None,
        ge=1,
        description="Override cache TTL for this tool in seconds. Null = global default.",
    )


class ToolPermissionUpdate(BaseModel):
    """Request body for updating rate limits on an existing permission."""

    rate_limit_per_minute: int | None = Field(
        None,
        ge=1,
        description="Max calls per minute. Null = unlimited.",
    )
    cache_ttl_seconds: int | None = Field(
        None,
        ge=1,
        description="Cache TTL override in seconds. Null = global default.",
    )


class ToolPermissionResponse(BaseModel):
    """Response schema for a tool permission record."""

    id: uuid.UUID
    agent_id: uuid.UUID
    mcp_server_id: uuid.UUID
    tool_name: str
    granted_at: datetime
    granted_by: str | None
    rate_limit_per_minute: int | None
    cache_ttl_seconds: int | None

    model_config = {"from_attributes": True}


class ToolPermissionEventResponse(BaseModel):
    """Response schema for a permission audit event."""

    id: uuid.UUID
    permission_id: uuid.UUID | None
    mcp_server_id: uuid.UUID | None
    tool_name: str
    action: str
    performed_by: str | None
    changes: dict[str, Any] | None
    occurred_at: datetime

    model_config = {"from_attributes": True}


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _log_event(
    db: AsyncSession,
    *,
    action: str,
    permission: ToolPermission,
    current_user: User,
    changes: dict[str, Any] | None = None,
) -> None:
    event = ToolPermissionEvent(
        org_id=permission.org_id,
        agent_id=permission.agent_id,
        permission_id=permission.id,
        mcp_server_id=permission.mcp_server_id,
        tool_name=permission.tool_name,
        action=action,
        performed_by=current_user.display_name or current_user.email,
        performed_by_user_id=current_user.id,
        changes=changes,
    )
    db.add(event)


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
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.org_id == current_user.org_id, Agent.is_active.is_(True))
    )
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")

    server_result = await db.execute(
        select(MCPServer).where(
            MCPServer.id == body.mcp_server_id,
            MCPServer.org_id == current_user.org_id,
            MCPServer.is_active.is_(True),
        )
    )
    if server_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server {body.mcp_server_id} not found")

    permission = ToolPermission(
        org_id=current_user.org_id,
        agent_id=agent_id,
        mcp_server_id=body.mcp_server_id,
        tool_name=body.tool_name,
        rate_limit_per_minute=body.rate_limit_per_minute,
        cache_ttl_seconds=body.cache_ttl_seconds,
        granted_by=current_user.display_name or current_user.email,
        granted_by_user_id=current_user.id,
    )
    db.add(permission)

    try:
        await db.flush()  # get permission.id before logging
        await _log_event(db, action="granted", permission=permission, current_user=current_user)
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
    "/{agent_id}/permissions/history",
    response_model=Page[ToolPermissionEventResponse],
    summary="Audit log for an agent's permissions",
)
async def list_permission_history(
    agent_id: uuid.UUID,
    skip: int = 0,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[ToolPermissionEventResponse]:
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.org_id == current_user.org_id, Agent.is_active.is_(True))
    )
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")

    total = await db.scalar(
        select(func.count(ToolPermissionEvent.id)).where(ToolPermissionEvent.agent_id == agent_id)
    ) or 0
    result = await db.execute(
        select(ToolPermissionEvent)
        .where(ToolPermissionEvent.agent_id == agent_id)
        .order_by(ToolPermissionEvent.occurred_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return Page(items=[ToolPermissionEventResponse.model_validate(e) for e in result.scalars().all()], total=total, skip=skip, limit=limit)


@router.get(
    "/{agent_id}/permissions",
    response_model=Page[ToolPermissionResponse],
    summary="List permissions for an agent",
)
async def list_tool_permissions(
    agent_id: uuid.UUID,
    skip: int = 0,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[ToolPermissionResponse]:
    agent_result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.org_id == current_user.org_id, Agent.is_active.is_(True))
    )
    if agent_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Agent {agent_id} not found")

    total = await db.scalar(
        select(func.count(ToolPermission.id)).where(ToolPermission.agent_id == agent_id)
    ) or 0
    result = await db.execute(
        select(ToolPermission).where(ToolPermission.agent_id == agent_id).offset(skip).limit(limit)
    )
    return Page(items=[ToolPermissionResponse.model_validate(p) for p in result.scalars().all()], total=total, skip=skip, limit=limit)


@router.patch(
    "/{agent_id}/permissions/{permission_id}",
    response_model=ToolPermissionResponse,
    summary="Update rate limits on a tool permission",
)
async def update_tool_permission(
    agent_id: uuid.UUID,
    permission_id: uuid.UUID,
    body: ToolPermissionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> ToolPermissionResponse:
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

    changes: dict[str, Any] = {}
    if permission.rate_limit_per_minute != body.rate_limit_per_minute:
        changes["rate_limit_per_minute"] = [permission.rate_limit_per_minute, body.rate_limit_per_minute]
    if permission.cache_ttl_seconds != body.cache_ttl_seconds:
        changes["cache_ttl_seconds"] = [permission.cache_ttl_seconds, body.cache_ttl_seconds]

    permission.rate_limit_per_minute = body.rate_limit_per_minute
    permission.cache_ttl_seconds = body.cache_ttl_seconds

    if changes:
        await _log_event(db, action="updated", permission=permission, current_user=current_user, changes=changes)

    await db.commit()
    await db.refresh(permission)
    return ToolPermissionResponse.model_validate(permission)


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

    await _log_event(db, action="revoked", permission=permission, current_user=current_user)
    await db.delete(permission)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
