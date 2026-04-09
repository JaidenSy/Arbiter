"""
NexusAI — API endpoints: Vault.

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

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.db.models.user import User
from app.db.models.vault import VaultSecret
from app.services.vault.vault_service import VaultService

# TODO(billing): Enforce vault_secrets plan limit here once check_resource_limit
# supports models without an is_active column. VaultSecret has org_id but no
# is_active — calling check_resource_limit(model=VaultSecret, ...) would raise
# AttributeError on the model.is_active clause in plan_service.py.
# Options: (a) add is_active to VaultSecret, (b) add a separate count helper
# to plan_service that omits the is_active filter for non-soft-delete models.

router = APIRouter(prefix="/vault", tags=["vault"])


# ── Inline schemas ────────────────────────────────────────────────────────────


class SecretCreate(BaseModel):
    """Request body for storing a secret."""

    name: str = Field(..., description="Logical key, e.g. GITHUB_TOKEN")
    value: str = Field(..., description="Raw secret value — will be encrypted at rest")


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
    current_user: User = Depends(get_current_user),
) -> SecretResponse:
    service = VaultService(db)
    secret = await service.store_secret(body.name, body.value, None, current_user.org_id)
    return SecretResponse.model_validate(secret)


@router.get(
    "/secrets",
    response_model=list[SecretResponse],
    summary="List secret names",
)
async def list_secrets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SecretResponse]:
    result = await db.execute(select(VaultSecret).where(VaultSecret.org_id == current_user.org_id))
    secrets = result.scalars().all()
    return [SecretResponse.model_validate(s) for s in secrets]


@router.get(
    "/secrets/{secret_id}",
    response_model=SecretValueResponse,
    summary="Retrieve and decrypt a secret",
)
async def get_secret(
    secret_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SecretValueResponse:
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
    current_user: User = Depends(get_current_user),
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
