"""
Arbiter — API endpoints: Vault.

Manages encrypted secrets stored in the vault.  Raw secret values are
accepted on write and returned on read — the gateway handles encryption
transparently.  Only admins should have access to these endpoints in
production (enforce via RBAC or network policy).

Routes:
    POST   /vault/secrets          — store (or rotate) a secret
    GET    /vault/secrets          — list secret names (no values)
    GET    /vault/secrets/{id}     — retrieve and decrypt a secret
    DELETE /vault/secrets/{id}     — permanently delete a secret
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, get_redis, require_role
from app.schemas.pagination import Page
from app.db.models.agent import Agent
from app.db.models.organization import Organization
from app.db.models.user import User
from app.db.models.vault import VaultSecret
from app.services.plan.plan_service import check_resource_limit
from app.services.vault.vault_service import VaultService

logger = logging.getLogger(__name__)

_VAULT_DECRYPT_RATE_LIMIT = 10  # requests per minute per user

router = APIRouter(prefix="/vault", tags=["vault"])


# ── Inline schemas ────────────────────────────────────────────────────────────


_SECRET_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


class SecretCreate(BaseModel):
    """Request body for storing a secret."""

    name: str = Field(..., min_length=1, max_length=128, description="Logical key, e.g. GITHUB_TOKEN")
    value: str = Field(..., min_length=1, max_length=10000, description="Raw secret value — will be encrypted at rest")
    agent_id: uuid.UUID | None = Field(None, description="Scope the secret to a specific agent")

    @field_validator("name")
    @classmethod
    def validate_name_format(cls, v: str) -> str:
        if not _SECRET_NAME_RE.match(v):
            raise ValueError(
                "Secret name must contain only letters, numbers, and underscores (A-Za-z0-9_). "
                "This must match the {{SECRET_NAME}} placeholder syntax used in tool call parameters."
            )
        return v


class SecretResponse(BaseModel):
    """Response when listing secrets — never exposes the value."""

    id: uuid.UUID
    name: str
    agent_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SecretValueResponse(SecretResponse):
    """Response for GET /vault/secrets/{id} — includes decrypted value."""

    value: str = Field(..., description="Decrypted secret value")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/secrets",
    response_model=SecretResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Store or rotate a secret",
)
async def create_secret(
    body: SecretCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> SecretResponse:
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=500, detail="Org not found")

    # If agent_id provided, verify it belongs to this org (prevent cross-org secret injection)
    agent_id: uuid.UUID | None = None
    if body.agent_id is not None:
        agent_result = await db.execute(
            select(Agent).where(
                Agent.id == body.agent_id,
                Agent.org_id == current_user.org_id,
                Agent.is_active.is_(True),
            )
        )
        agent = agent_result.scalar_one_or_none()
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {body.agent_id} not found",
            )
        agent_id = body.agent_id

    await check_resource_limit(
        db=db,
        org=org,
        resource="vault_secrets",
        model=VaultSecret,
        filter_col=VaultSecret.org_id,
        count_active_only=False,
    )
    service = VaultService(db)
    secret = await service.store_secret(body.name, body.value, agent_id, current_user.org_id)
    return SecretResponse.model_validate(secret)


@router.get(
    "/secrets",
    response_model=Page[SecretResponse],
    summary="List secret names",
)
async def list_secrets(
    agent_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[SecretResponse]:
    filters = [VaultSecret.org_id == current_user.org_id]
    if agent_id is not None:
        filters.append(VaultSecret.agent_id == agent_id)
    total = await db.scalar(select(func.count(VaultSecret.id)).where(*filters)) or 0
    result = await db.execute(select(VaultSecret).where(*filters).offset(skip).limit(limit))
    secrets = result.scalars().all()
    return Page(items=[SecretResponse.model_validate(s) for s in secrets], total=total, skip=skip, limit=limit)


@router.get(
    "/secrets/{secret_id}",
    response_model=SecretValueResponse,
    summary="Retrieve and decrypt a secret",
)
async def get_secret(
    secret_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
    current_user: User = Depends(require_role("owner", "admin")),
) -> SecretValueResponse:
    minute_bucket = int(time.time() // 60)
    rl_key = f"rate_limit:vault_decrypt:{current_user.id}:{minute_bucket}"
    count = await redis.incr(rl_key)
    if count == 1:
        await redis.expire(rl_key, 120)
    if count > _VAULT_DECRYPT_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded: vault decrypt allows 10 requests per minute",
        )

    result = await db.execute(
        select(VaultSecret).where(
            VaultSecret.id == secret_id,
            VaultSecret.org_id == current_user.org_id,
        )
    )
    secret = result.scalar_one_or_none()
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret {secret_id} not found",
        )

    service = VaultService(db)
    value = service.decrypt(secret.ciphertext)
    logger.info(
        "vault: decrypt secret_id=%s name=%s user=%s org=%s",
        secret_id,
        secret.name,
        current_user.id,
        current_user.org_id,
    )
    # SECURITY: value is never logged — only passed to the response serialiser.
    return SecretValueResponse(
        id=secret.id,
        name=secret.name,
        agent_id=secret.agent_id,
        created_at=secret.created_at,
        value=value,
    )


@router.delete(
    "/secrets/{secret_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a secret",
)
async def delete_secret(
    secret_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Response:
    result = await db.execute(
        select(VaultSecret).where(
            VaultSecret.id == secret_id,
            VaultSecret.org_id == current_user.org_id,
        )
    )
    secret = result.scalar_one_or_none()
    if secret is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Secret {secret_id} not found",
        )

    await db.delete(secret)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
