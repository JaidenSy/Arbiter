# Copyright (c) 2026 Jaiden Sy. All rights reserved.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Arbiter — API endpoints: CLI Device Flow Auth.

Implements the OAuth2 device authorization grant (RFC 8628) so the Arbiter
CLI can authenticate without a browser redirect.  The three-step flow is:

1. CLI calls POST /auth/cli/device  → receives device_code + user_code
2. User opens browser, visits /cli-auth?code=<user_code>, approves via
   PATCH /auth/cli/device/{user_code}/approve
3. CLI polls POST /auth/cli/token with device_code until it receives a JWT

Routes:
    POST   /auth/cli/device                        → 201  initiate device flow
    POST   /auth/cli/token                         → 200  poll for CLI token
    PATCH  /auth/cli/device/{user_code}/approve    → 200  approve (auth required)
    PATCH  /auth/cli/device/{user_code}/deny       → 200  deny   (auth required)
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security as _sec
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.db.models.cli_device_code import CliDeviceCode
from app.db.models.user import User

router = APIRouter(prefix="/auth/cli", tags=["cli-auth"])

# ── Constants ─────────────────────────────────────────────────────────────────

_DEVICE_CODE_TTL_SECONDS = 900  # 15 minutes

_USER_CODE_WORDS = [
    "TIGER",
    "CLOUD",
    "RIVER",
    "STORM",
    "PIXEL",
    "LANCE",
    "NOVA",
    "FROST",
    "EMBER",
    "SWIFT",
]

_VERIFICATION_URI = "https://arbiterai.dev/cli-auth"


# ── Request / response schemas ────────────────────────────────────────────────


class DeviceCodeResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int


class TokenRequest(BaseModel):
    device_code: str


class CliTokenResponse(BaseModel):
    access_token: str
    token_type: str
    org_id: str


class MessageResponse(BaseModel):
    message: str


# ── Helpers ───────────────────────────────────────────────────────────────────


def _generate_user_code() -> str:
    """Return a random user code in the format WORD-NNNN."""
    word = random.choice(_USER_CODE_WORDS)  # noqa: S311 — not cryptographic
    digits = random.randint(1000, 9999)  # noqa: S311
    return f"{word}-{digits}"


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/device",
    response_model=DeviceCodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate CLI device authorization flow",
)
async def initiate_device_flow(
    db: AsyncSession = Depends(get_db),
) -> DeviceCodeResponse:
    """
    Generate a device_code and user_code for the CLI device flow.

    The CLI displays the user_code to the user, who visits the verification URI
    and approves the request.  The CLI then polls POST /auth/cli/token with the
    device_code until a JWT is issued or the code expires.
    """
    device_code = str(uuid.uuid4())
    user_code = _generate_user_code()
    expires_at = datetime.now(tz=UTC) + timedelta(seconds=_DEVICE_CODE_TTL_SECONDS)

    record = CliDeviceCode(
        device_code=device_code,
        user_code=user_code,
        status="pending",
        expires_at=expires_at,
    )
    db.add(record)
    await db.commit()

    return DeviceCodeResponse(
        device_code=device_code,
        user_code=user_code,
        verification_uri=_VERIFICATION_URI,
        expires_in=_DEVICE_CODE_TTL_SECONDS,
    )


@router.post(
    "/token",
    response_model=CliTokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Poll for CLI access token after device authorization",
)
async def poll_for_token(
    body: TokenRequest,
    db: AsyncSession = Depends(get_db),
) -> CliTokenResponse:
    """
    Exchange an approved device_code for a long-lived CLI JWT.

    Response codes:
        200 — authorization approved; JWT returned.
        404 — device_code not found.
        410 — code expired or rejected.
        428 — authorization still pending; caller should retry.
    """
    record = await db.scalar(
        select(CliDeviceCode).where(CliDeviceCode.device_code == body.device_code)
    )

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="device_code not found",
        )

    now = datetime.now(tz=UTC)

    # Treat rejected codes as expired — do not reveal the distinction to the CLI.
    if record.status == "rejected":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="code_expired_or_rejected",
        )

    # Expire stale pending/approved codes.
    if record.expires_at.replace(tzinfo=UTC) <= now:
        if record.status not in ("expired", "consumed"):
            record.status = "expired"
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="code_expired_or_rejected",
        )

    if record.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="authorization_pending",
        )

    if record.status == "consumed":
        # Already issued — treat as expired to prevent replay.
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="code_expired_or_rejected",
        )

    # status == "approved" — issue token and consume the record.
    if record.user_id is None or record.org_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="approved device code is missing user or org — data integrity error",
        )

    user = await db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or not found",
        )

    access_token = _sec.create_cli_access_token(
        user_id=record.user_id,
        org_id=record.org_id,
        role=user.role,
        expire_minutes=settings.cli_token_expire_minutes,
    )

    record.status = "consumed"
    await db.commit()

    return CliTokenResponse(
        access_token=access_token,
        token_type="bearer",
        org_id=str(record.org_id),
    )


@router.patch(
    "/device/{user_code}/approve",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve a pending CLI device authorization request",
)
async def approve_device(
    user_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Authorize a CLI session by approving the device code displayed in the terminal.

    The authenticated user's identity and org are bound to the device code so
    the CLI receives a token scoped to the correct org on the next poll.
    """
    record = await db.scalar(select(CliDeviceCode).where(CliDeviceCode.user_code == user_code))

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_code not found",
        )

    now = datetime.now(tz=UTC)

    if record.expires_at.replace(tzinfo=UTC) <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="code_expired",
        )

    if record.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="code_already_used",
        )

    record.status = "approved"
    record.user_id = current_user.id
    record.org_id = current_user.org_id
    record.approved_at = now
    await db.commit()

    return MessageResponse(message="CLI authorized successfully")


@router.patch(
    "/device/{user_code}/deny",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Deny a pending CLI device authorization request",
)
async def deny_device(
    user_code: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Reject a CLI device code.  The next CLI poll will receive 410 Gone.

    The current_user dependency is required to ensure only authenticated users
    can trigger a denial — prevents unauthenticated code invalidation.
    """
    record = await db.scalar(select(CliDeviceCode).where(CliDeviceCode.user_code == user_code))

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user_code not found",
        )

    if record.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="code_already_used",
        )

    record.status = "rejected"
    await db.commit()

    return MessageResponse(message="CLI authorization denied")
