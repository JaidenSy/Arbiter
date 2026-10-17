# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
Arbiter API endpoints: Tool-definition pins (rug-pull defense, OWASP MCP03).

The gateway pins each upstream tool's {name, description, inputSchema} the
first time it is listed.  A later tools/list with a different definition
marks the tool ``changed`` until an org admin approves it here.

Routes:
    GET  /tool-definitions                 : list pinned tools (filter by status/server)
    POST /tool-definitions/{id}/approve    : accept the current definition as the new pin
    GET  /tool-definitions/policy          : org default policy for changed tools
    PUT  /tool-definitions/policy          : set the org default ('allow' | 'block')

Per-server overrides are set with ``tool_change_policy`` on
POST/PATCH /mcp-servers.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.db.models.organization import Organization
from app.db.models.tool_definition import ToolDefinition
from app.db.models.user import User
from app.schemas.pagination import Page
from app.services.tool_pin.tool_pin_service import ToolPinService

router = APIRouter(prefix="/tool-definitions", tags=["tool-definitions"])


class ToolDefinitionResponse(BaseModel):
    id: uuid.UUID
    mcp_server_id: uuid.UUID
    tool_name: str
    status: str
    approved_hash: str
    current_hash: str
    approved_definition: dict[str, Any]
    current_definition: dict[str, Any]
    first_seen_at: datetime
    last_seen_at: datetime
    changed_at: datetime | None = None
    approved_at: datetime | None = None
    approved_by_user_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class ToolChangePolicy(BaseModel):
    policy: Literal["allow", "block"]


@router.get(
    "",
    response_model=Page[ToolDefinitionResponse],
    summary="List pinned tool definitions (e.g. ?status=changed for pending re-approval)",
)
async def list_tool_definitions(
    status_filter: Literal["approved", "changed"] | None = Query(None, alias="status"),
    server_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[ToolDefinitionResponse]:
    limit = min(limit, 200)
    conditions = [ToolDefinition.org_id == current_user.org_id]
    if status_filter is not None:
        conditions.append(ToolDefinition.status == status_filter)
    if server_id is not None:
        conditions.append(ToolDefinition.mcp_server_id == server_id)

    total = await db.scalar(select(func.count(ToolDefinition.id)).where(*conditions)) or 0
    result = await db.execute(
        select(ToolDefinition)
        .where(*conditions)
        .order_by(ToolDefinition.changed_at.desc().nulls_last(), ToolDefinition.tool_name)
        .offset(skip)
        .limit(limit)
    )
    rows = result.scalars().all()
    return Page(
        items=[ToolDefinitionResponse.model_validate(r) for r in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/policy",
    response_model=ToolChangePolicy,
    summary="Org default policy for calls to tools whose definition changed",
)
async def get_tool_change_policy(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ToolChangePolicy:
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return ToolChangePolicy(policy="block" if org.tool_change_policy == "block" else "allow")


@router.put(
    "/policy",
    response_model=ToolChangePolicy,
    summary="Set the org default policy for changed tools ('allow' or 'block')",
)
async def set_tool_change_policy(
    body: ToolChangePolicy,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> ToolChangePolicy:
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    org.tool_change_policy = body.policy
    await db.commit()
    return ToolChangePolicy(policy=body.policy)


@router.post(
    "/{definition_id}/approve",
    response_model=ToolDefinitionResponse,
    summary="Approve a changed tool definition as the new pin",
)
async def approve_tool_definition(
    definition_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> ToolDefinitionResponse:
    result = await db.execute(
        select(ToolDefinition).where(
            ToolDefinition.id == definition_id,
            ToolDefinition.org_id == current_user.org_id,
        )
    )
    pin = result.scalar_one_or_none()
    if pin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool definition {definition_id} not found",
        )
    pin = await ToolPinService(db).approve(pin, user_id=current_user.id)
    return ToolDefinitionResponse.model_validate(pin)
