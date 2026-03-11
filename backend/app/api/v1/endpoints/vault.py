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

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_agent, get_db
from app.db.models.agent import Agent
from app.db.models.vault import VaultSecret
from app.services.vault.vault_service import VaultService

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
    current_agent: Agent = Depends(get_current_agent),
) -> SecretResponse:
    """
    Encrypt and store a secret in the vault, scoped to the calling agent.

    If a secret with the same name already exists for this agent, it is
    overwritten (rotation).  The previous ciphertext is not retained.

    Args:
        body:          Secret name and plaintext value.
        db:            Injected DB session.
        current_agent: Authenticated agent — secret is scoped to this agent.

    Returns:
        SecretResponse: Metadata only — value is not echoed back.
    """
    service = VaultService(db)
    secret = await service.store_secret(body.name, body.value, current_agent.id)
    return SecretResponse.model_validate(secret)


@router.get(
    "/secrets",
    response_model=list[SecretResponse],
    summary="List secret names",
)
async def list_secrets(
    db: AsyncSession = Depends(get_db),
    current_agent: Agent = Depends(get_current_agent),
) -> list[SecretResponse]:
    """
    Return all secret names and IDs owned by the calling agent.

    Never exposes decrypted values.  Scoped to current_agent.id for security —
    agents cannot enumerate each other's secrets.

    Args:
        db:            Injected DB session.
        current_agent: Authenticated agent.

    Returns:
        list[SecretResponse]: All vault secrets for this agent (no values).
    """
    result = await db.execute(
        select(VaultSecret).where(VaultSecret.agent_id == current_agent.id)
    )
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
    current_agent: Agent = Depends(get_current_agent),
) -> SecretValueResponse:
    """
    Fetch and decrypt a secret by UUID.

    Caution: This endpoint returns the plaintext value.  Restrict access
    via network policy or a separate admin RBAC role.  The secret must be
    owned by the calling agent — agents cannot read each other's secrets.

    Args:
        secret_id:     UUID of the vault secret.
        db:            Injected DB session.
        current_agent: Authenticated agent.

    Returns:
        SecretValueResponse: Metadata plus decrypted value.

    Raises:
        HTTPException 404: If the secret does not exist or belongs to another agent.
    """
    result = await db.execute(
        select(VaultSecret).where(
            VaultSecret.id == secret_id,
            VaultSecret.agent_id == current_agent.id,
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
    current_agent: Agent = Depends(get_current_agent),
) -> None:
    """
    Permanently delete a secret from the vault.

    Unlike agents/servers, secrets are hard-deleted (no soft-delete).
    The secret must be owned by the calling agent.

    Args:
        secret_id:     UUID of the secret to delete.
        db:            Injected DB session.
        current_agent: Authenticated agent.

    Raises:
        HTTPException 404: If the secret does not exist or belongs to another agent.
    """
    result = await db.execute(
        select(VaultSecret).where(
            VaultSecret.id == secret_id,
            VaultSecret.agent_id == current_agent.id,
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
