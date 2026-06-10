"""
Arbiter — Webhook delivery service.

Dispatches signed payloads to registered webhook URLs with retry/backoff.
Called from event triggers in proxy, quota, and health-check code paths.

Signing: HMAC-SHA256 over the JSON body; sent as X-Arbiter-Signature: sha256=<hex>
Delivery: up to 3 attempts with 1s→2s→4s exponential backoff.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.webhook import Webhook, WebhookDeliveryLog

_LOG = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_BASE = 1.0  # seconds; doubles each retry


async def dispatch_event(
    db: AsyncSession,
    org_id: uuid.UUID,
    event_type: str,
    payload: dict,
) -> None:
    """
    Fire-and-forget: find active webhooks subscribed to event_type and deliver.

    Safe to call without awaiting from background tasks — all errors are caught
    and logged; no exception propagates to the caller.
    """
    result = await db.execute(
        select(Webhook).where(
            Webhook.org_id == org_id,
            Webhook.is_active.is_(True),
        )
    )
    hooks = result.scalars().all()
    matching = [h for h in hooks if event_type in (h.events or [])]

    if not matching:
        return

    full_payload = {
        "event": event_type,
        "org_id": str(org_id),
        "timestamp": datetime.now(UTC).isoformat(),
        "data": payload,
    }

    for hook in matching:
        asyncio.create_task(_deliver_with_retry(db, hook, event_type, full_payload))


async def _deliver_with_retry(
    db: AsyncSession,
    hook: Webhook,
    event_type: str,
    payload: dict,
) -> None:
    body = json.dumps(payload, default=str)
    sig = _sign(hook.secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-Arbiter-Signature": f"sha256={sig}",
        "X-Arbiter-Event": event_type,
    }

    last_error: str | None = None
    last_status: int | None = None
    last_body: str | None = None

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                resp = await client.post(hook.url, content=body, headers=headers)
                last_status = resp.status_code
                last_body = resp.text[:2000]
                last_error = None
                if resp.is_success:
                    await _log_delivery(
                        db, hook.id, event_type, payload, last_status, last_body, None, attempt
                    )
                    return
                _LOG.warning(
                    "Webhook %s returned %d (attempt %d/%d)",
                    hook.id,
                    resp.status_code,
                    attempt,
                    _MAX_ATTEMPTS,
                )
            except Exception as exc:
                last_error = str(exc)
                last_status = None
                last_body = None
                _LOG.warning(
                    "Webhook %s delivery error (attempt %d/%d): %s",
                    hook.id,
                    attempt,
                    _MAX_ATTEMPTS,
                    exc,
                )

            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(_BACKOFF_BASE * (2 ** (attempt - 1)))

    await _log_delivery(
        db, hook.id, event_type, payload, last_status, last_body, last_error, _MAX_ATTEMPTS
    )


async def _log_delivery(
    db: AsyncSession,
    webhook_id: uuid.UUID,
    event_type: str,
    payload: dict,
    response_status: int | None,
    response_body: str | None,
    error: str | None,
    attempt: int,
) -> None:
    try:
        log = WebhookDeliveryLog(
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
            response_status=response_status,
            response_body=response_body,
            error=error,
            attempt=attempt,
        )
        db.add(log)
        await db.commit()
    except Exception as exc:
        _LOG.error("Failed to persist webhook delivery log: %s", exc)


def _sign(secret: str, body: str) -> str:
    return hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
