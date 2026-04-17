"""
Nexvault — API endpoints: Onboarding.

Provides a lightweight status check so the dashboard can show a step-by-step
onboarding checklist after first login.

Routes:
    GET /onboarding/status → 200  { has_agent, has_server, has_permission, first_call_made }
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.agent import Agent
from app.db.models.mcp_server import MCPServer
from app.db.models.tool_permission import ToolPermission
from app.db.models.usage_event import UsageEvent
from app.db.models.user import User

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingStatus(BaseModel):
    """Onboarding checklist status for the authenticated user's org."""

    has_agent: bool
    has_server: bool
    has_permission: bool
    first_call_made: bool
    complete: bool  # True when the user has at least one agent and one server


@router.get(
    "/status",
    response_model=OnboardingStatus,
    status_code=status.HTTP_200_OK,
    summary="Get onboarding checklist status for the current org",
)
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OnboardingStatus:
    """
    Return a checklist of onboarding milestones scoped to the current user's org.

    Steps:
        has_agent:        At least one active agent exists in the org.
        has_server:       At least one active MCP server is registered.
        has_permission:   At least one tool permission has been granted.
        first_call_made:  At least one tool call has been recorded in usage_events.

    Args:
        current_user: Injected JWT-authenticated user.
        db:           Injected database session.

    Returns:
        OnboardingStatus: Four boolean flags.
    """
    org_id = current_user.org_id

    agent_count = await db.scalar(
        select(func.count()).where(
            Agent.org_id == org_id,
            Agent.is_active.is_(True),
        )
    )

    server_count = await db.scalar(
        select(func.count()).where(
            MCPServer.org_id == org_id,
            MCPServer.is_active.is_(True),
        )
    )

    permission_count = await db.scalar(
        select(func.count()).where(ToolPermission.org_id == org_id)
    )

    call_count = await db.scalar(
        select(func.sum(UsageEvent.tool_calls)).where(UsageEvent.org_id == org_id)
    )

    has_agent = bool(agent_count)
    has_server = bool(server_count)
    return OnboardingStatus(
        has_agent=has_agent,
        has_server=has_server,
        has_permission=bool(permission_count),
        first_call_made=bool(call_count and call_count > 0),
        complete=has_agent and has_server,
    )
