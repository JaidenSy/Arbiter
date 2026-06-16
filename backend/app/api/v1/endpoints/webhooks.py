"""
Arbiter — API endpoints: Webhooks.

Routes:
    POST   /webhooks          — create a webhook (Pro+)
    GET    /webhooks          — list webhooks
    PATCH  /webhooks/{id}     — update webhook
    DELETE /webhooks/{id}     — delete webhook
    GET    /webhooks/{id}/logs — delivery log for a webhook
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_role
from app.db.models.organization import Organization
from app.db.models.user import User
from app.db.models.webhook import WEBHOOK_EVENTS, Webhook, WebhookDeliveryLog
from app.services.plan.plan_limits import PAID_TIERS

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Schema ────────────────────────────────────────────────────────────────────


class WebhookCreate(BaseModel):
    url: str = Field(..., description="Destination URL for POST delivery")
    events: list[str] = Field(..., min_length=1, description="Event types to subscribe to")
    is_active: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        stripped = v.strip()
        if not (stripped.startswith("http://") or stripped.startswith("https://")):
            raise ValueError("url must be http:// or https://")
        return stripped

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str]) -> list[str]:
        invalid = set(v) - WEBHOOK_EVENTS
        if invalid:
            raise ValueError(
                f"Unknown event types: {sorted(invalid)}. Valid: {sorted(WEBHOOK_EVENTS)}"
            )
        return v


class WebhookUpdate(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        stripped = v.strip()
        if not (stripped.startswith("http://") or stripped.startswith("https://")):
            raise ValueError("url must be http:// or https://")
        return stripped

    @field_validator("events")
    @classmethod
    def validate_events(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        invalid = set(v) - WEBHOOK_EVENTS
        if invalid:
            raise ValueError(
                f"Unknown event types: {sorted(invalid)}. Valid: {sorted(WEBHOOK_EVENTS)}"
            )
        return v


class WebhookResponse(BaseModel):
    id: uuid.UUID
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime
    # secret is never returned after creation

    model_config = {"from_attributes": True}


class WebhookCreateResponse(WebhookResponse):
    secret: str  # returned only on create so caller can store it


class DeliveryLogResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    response_status: int | None
    error: str | None
    attempt: int
    delivered_at: datetime

    model_config = {"from_attributes": True}


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _require_pro(db: AsyncSession, org_id: uuid.UUID) -> None:
    org = await db.get(Organization, org_id)
    if not org or org.plan_tier not in PAID_TIERS:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Webhooks require a Pro or Enterprise plan",
        )


async def _get_webhook_or_404(
    db: AsyncSession, webhook_id: uuid.UUID, org_id: uuid.UUID
) -> Webhook:
    hook = await db.get(Webhook, webhook_id)
    if not hook or hook.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return hook


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=WebhookCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a webhook (Pro+)",
)
async def create_webhook(
    body: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> WebhookCreateResponse:
    await _require_pro(db, current_user.org_id)
    secret = secrets.token_hex(32)
    hook = Webhook(
        org_id=current_user.org_id,
        url=body.url,
        secret=secret,
        events=body.events,
        is_active=body.is_active,
    )
    db.add(hook)
    await db.commit()
    await db.refresh(hook)
    return WebhookCreateResponse(
        id=hook.id,
        url=hook.url,
        events=hook.events,
        is_active=hook.is_active,
        created_at=hook.created_at,
        secret=secret,
    )


@router.get(
    "",
    response_model=list[WebhookResponse],
    status_code=status.HTTP_200_OK,
    summary="List webhooks",
)
async def list_webhooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[WebhookResponse]:
    result = await db.execute(
        select(Webhook)
        .where(Webhook.org_id == current_user.org_id)
        .order_by(Webhook.created_at.desc())
    )
    return [WebhookResponse.model_validate(h) for h in result.scalars().all()]


@router.patch(
    "/{webhook_id}",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a webhook",
)
async def update_webhook(
    webhook_id: uuid.UUID,
    body: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> WebhookResponse:
    hook = await _get_webhook_or_404(db, webhook_id, current_user.org_id)
    if body.url is not None:
        hook.url = body.url
    if body.events is not None:
        hook.events = body.events
    if body.is_active is not None:
        hook.is_active = body.is_active
    await db.commit()
    await db.refresh(hook)
    return WebhookResponse.model_validate(hook)


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a webhook",
)
async def delete_webhook(
    webhook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "admin")),
) -> Response:
    hook = await _get_webhook_or_404(db, webhook_id, current_user.org_id)
    await db.delete(hook)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{webhook_id}/logs",
    response_model=list[DeliveryLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get delivery log for a webhook",
)
async def get_webhook_logs(
    webhook_id: uuid.UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DeliveryLogResponse]:
    await _get_webhook_or_404(db, webhook_id, current_user.org_id)
    result = await db.execute(
        select(WebhookDeliveryLog)
        .where(WebhookDeliveryLog.webhook_id == webhook_id)
        .order_by(WebhookDeliveryLog.delivered_at.desc())
        .limit(min(limit, 200))
    )
    return [DeliveryLogResponse.model_validate(r) for r in result.scalars().all()]
