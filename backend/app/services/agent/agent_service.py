# Copyright (c) 2026 Jaiden Sy. All rights reserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Arbiter — AgentService: agent lookup helpers.

Provides query helpers for the agents table used by other services and
endpoints.  Authentication / API-key validation lives in dependencies.py;
this module handles business-logic-level queries only.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent


async def get_agent_ids_by_owner(
    db: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    """
    Return the UUIDs of all agents in ``org_id`` that were created by ``user_id``.

    Used by the vault list endpoint to scope secret enumeration for
    ``member``-role users — they may only see secrets scoped to agents they
    own (Issue #264).

    Args:
        db:      Async SQLAlchemy session.
        org_id:  Organization UUID — ensures cross-org isolation.
        user_id: The creating user's UUID.

    Returns:
        list[uuid.UUID]: Possibly empty list of agent UUIDs.
    """
    result = await db.execute(
        select(Agent.id).where(
            Agent.org_id == org_id,
            Agent.created_by_user_id == user_id,
        )
    )
    return list(result.scalars().all())
