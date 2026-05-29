"""
Arbiter — API endpoints: Auth.

Routes:
    POST   /auth/register           → 201  issue tokens for new org + owner
    POST   /auth/login              → 200  issue tokens for existing user
    POST   /auth/refresh            → 200  rotate refresh token, issue fresh pair
    POST   /auth/logout             → 204  invalidate access token; optionally all devices
    GET    /auth/me                 → 200  current user profile
    PATCH  /auth/me                 → 200  update display name or email
    POST   /auth/me/change-password → 204  change password (password users only)
    DELETE /auth/me                 → 204  deactivate account + revoke all tokens
"""

from __future__ import annotations

import hmac

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, EmailStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import security as _sec
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db, get_redis
from app.db.models.organization import Organization
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
)
from app.services.auth import auth_service
from app.services.email.email_service import (
    send_email_change_confirmation,
    send_email_verification,
    send_password_reset,
)

_token_serializer = URLSafeTimedSerializer(settings.app_secret_key)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _build_me_response(user: User, db: AsyncSession) -> MeResponse:
    """Load org + social accounts and assemble MeResponse."""
    # Reload user with social_accounts eagerly to avoid lazy-load issues in async
    user_with_socials = await db.scalar(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.social_accounts))
    )
    if user_with_socials is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    org = await db.get(Organization, user.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Organization not found",
        )

    linked_providers = [sa.provider for sa in user_with_socials.social_accounts]
    avatar_url = next(
        (sa.avatar_url for sa in user_with_socials.social_accounts if sa.avatar_url),
        None,
    )

    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        org_id=user.org_id,
        org_name=org.name,
        org_plan=org.plan_tier,
        has_password=bool(user.hashed_password),
        linked_providers=linked_providers,
        avatar_url=avatar_url,
        is_verified=user.is_verified,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new organization and owner account",
)
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenResponse:
    if not settings.allow_public_registration:
        if not settings.invite_code or not hmac.compare_digest(body.invite_code, settings.invite_code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration requires a valid invite code",
            )

    # Org creation rate limit — max 3 new orgs per IP per day to prevent
    # free-tier reset abuse (register new email → new org → reset quota).
    if redis is not None:
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown").split(",")[0].strip()
        reg_key = f"org_reg:{client_ip}:{date.today().isoformat()}"
        reg_count = await redis.incr(reg_key)
        if reg_count == 1:
            await redis.expire(reg_key, 86400)  # 24-hour window
        if reg_count > 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many accounts created from this IP. Try again tomorrow.",
            )

    user, access_token, refresh_token = await auth_service.register(
        db=db,
        org_name=body.org_name,
        email=body.email,
        password=body.password,
    )

    token = _token_serializer.dumps(str(user.id), salt="email-verify")
    verify_url = f"{settings.frontend_url}/verify-email?token={token}"
    await send_email_verification(user.email, verify_url)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and receive a token pair",
)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenResponse:
    if redis is not None:
        # Per-email rate limit — 10 attempts per 15 minutes
        rate_key = f"login_attempts:{body.email}"
        attempts = await redis.incr(rate_key)
        if attempts == 1:
            await redis.expire(rate_key, 900)  # 15-minute window
        if attempts > 10:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again in 15 minutes.",
            )

        # Per-IP rate limit — 20 attempts per 10 minutes (credential stuffing defence)
        client_ip = request.headers.get(
            "X-Forwarded-For", request.client.host if request.client else "unknown"
        ).split(",")[0].strip()
        ip_key = f"login_ip:{client_ip}"
        ip_attempts = await redis.incr(ip_key)
        if ip_attempts == 1:
            await redis.expire(ip_key, 600)  # 10-minute window
        if ip_attempts > 20:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts from this IP. Try again in 10 minutes.",
            )

    _user, access_token, refresh_token = await auth_service.login(
        db=db,
        email=body.email,
        password=body.password,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue a fresh access token",
)
async def refresh(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenResponse:
    new_access, new_refresh = await auth_service.refresh_tokens(
        db=db,
        redis=redis,
        raw_token=body.refresh_token,
    )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate the current session",
)
async def logout(
    all_devices: bool = Query(
        default=False,
        alias="all",
        description="Revoke all sessions for this user",
    ),
    authorization: str | None = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> Response:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    token = authorization.removeprefix("Bearer ").strip()
    payload = _sec.decode_access_token(token)

    await auth_service.logout(
        db=db,
        redis=redis,
        jti=payload.get("jti", ""),
        exp=payload.get("exp", 0),
        user_id=current_user.id,
        all_devices=all_devices,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MeResponse:
    return await _build_me_response(current_user, db)


class UpdateMeResponse(MeResponse):
    """Extended response for PATCH /auth/me when an email change is pending."""
    pending_email_confirmation: str | None = None


@router.patch(
    "/me",
    response_model=UpdateMeResponse,
    status_code=status.HTTP_200_OK,
    summary="Update display name or email",
)
async def update_me(
    body: UpdateMeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UpdateMeResponse:
    pending_email: str | None = None

    if body.email and str(body.email) != current_user.email:
        new_email = str(body.email)
        existing = await db.scalar(select(User).where(User.email == new_email))
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That email is already in use",
            )
        # Don't update email yet — send a confirmation link to the new address
        token = _token_serializer.dumps(
            {"uid": str(current_user.id), "email": new_email},
            salt="email-change",
        )
        confirm_url = f"{settings.frontend_url}/confirm-email-change?token={token}"
        await send_email_change_confirmation(new_email, confirm_url)
        pending_email = new_email

    if body.display_name is not None:
        current_user.display_name = body.display_name
        await db.commit()
        await db.refresh(current_user)

    me = await _build_me_response(current_user, db)
    return UpdateMeResponse(**me.model_dump(), pending_email_confirmation=pending_email)


@router.post(
    "/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password (email/password accounts only)",
)
async def change_password(
    body: ChangePasswordRequest,
    authorization: str | None = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> Response:
    if not current_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses SSO — password change is not available",
        )

    if not _sec.verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = _sec.hash_password(body.new_password)

    # Revoke all refresh tokens so existing sessions cannot be re-used.
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == current_user.id))

    await db.commit()

    # Blocklist the current access token so it is rejected immediately.
    if authorization and redis is not None:
        try:
            raw_token = authorization.removeprefix("Bearer ").strip()
            payload = _sec.decode_access_token(raw_token)
            jti: str = payload.get("jti", "")
            exp: int = payload.get("exp", 0)
            if jti:
                now = int(datetime.now(tz=timezone.utc).timestamp())
                ttl = max(exp - now, 1)
                await redis.setex(f"jti_blocklist:{jti}", ttl, "")
        except Exception:
            pass  # best-effort; password is already changed

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="GDPR-compliant account deletion — anonymize PII and hard-delete related data",
)
async def delete_me(
    authorization: str | None = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> Response:
    import asyncio
    import logging
    from datetime import datetime, timezone

    import stripe
    import stripe.error
    from sqlalchemy import delete, func as sqlfunc, update

    from app.db.models.agent import Agent
    from app.db.models.cache import CacheEntry
    from app.db.models.gdpr_deletion_log import GdprDeletionLog
    from app.db.models.mcp_server import MCPServer
    from app.db.models.org_invite import OrgInvite
    from app.db.models.session import Session, SessionEvent
    from app.db.models.social_account import SocialAccount
    from app.db.models.vault import VaultSecret

    _log = logging.getLogger(__name__)

    # Capture identifiers and original email BEFORE any mutation.
    user_id = current_user.id
    org_id = current_user.org_id
    original_email = current_user.email

    # ── Step 1: Cancel Stripe subscription (best-effort, before DB changes) ──
    org = await db.get(Organization, org_id)
    had_stripe_subscription = bool(org is not None and org.stripe_subscription_id)
    if org is not None and org.stripe_subscription_id and settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key
        try:
            await asyncio.to_thread(
                stripe.Subscription.cancel,
                org.stripe_subscription_id,
            )
            org.stripe_subscription_id = None
            org.plan_tier = "free"
        except stripe.error.InvalidRequestError:
            # Already cancelled or not found — clear the stale ID and continue.
            org.stripe_subscription_id = None
            org.plan_tier = "free"
        except stripe.error.StripeError as exc:
            _log.warning("delete_me: Stripe cancellation failed (continuing): %s", exc)

    # ── Step 2: Anonymize user PII (FIX-1) ───────────────────────────────────
    current_user.email = f"deleted-{user_id}@gdpr.invalid"
    current_user.display_name = None
    current_user.hashed_password = ""
    current_user.is_active = False
    current_user.is_verified = False

    # ── Step 3: Hard delete social_accounts (FIX-2) ──────────────────────────
    await db.execute(delete(SocialAccount).where(SocialAccount.user_id == user_id))

    # ── Step 4: Delete org_invites for this user's email (FIX-6) ─────────────
    # Done before org ownership check so invites are cleaned up regardless.
    await db.execute(delete(OrgInvite).where(OrgInvite.email == original_email))

    # ── Step 5: Hard delete refresh tokens (FIX-4) ───────────────────────────
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))

    # ── Step 6: Org ownership check and cleanup (FIX-3) ──────────────────────
    if org is not None:
        # Count remaining owners in the org (excluding the deleting user).
        other_owner_count = await db.scalar(
            select(sqlfunc.count(User.id)).where(
                User.org_id == org_id,
                User.role == "owner",
                User.id != user_id,
                User.is_active.is_(True),
            )
        )

        if other_owner_count == 0:
            # This user is the sole owner — delete all org resources, then the org.
            # Explicit deletes for tables that do NOT cascade directly from org
            # or that need to be cleared before the org row is removed.
            await db.execute(delete(VaultSecret).where(VaultSecret.org_id == org_id))
            await db.execute(delete(CacheEntry).where(CacheEntry.org_id == org_id))

            # Sessions and SessionEvents cascade from org via ON DELETE CASCADE;
            # Agents and ToolPermissions also cascade. Deleting the org row
            # triggers the DB-level cascade for all remaining child tables.
            # Anonymize org before deletion to scrub billing PII.
            org.stripe_customer_id = None
            org.name = f"deleted-org-{org_id}"

            # P2-FIX-6: Anonymize session events for this user before org cascade.
            await db.execute(
                update(SessionEvent)
                .where(
                    SessionEvent.org_id == org_id,
                    SessionEvent.user_id == user_id,
                )
                .values(user_id=None, request_payload=None, response_payload=None)
            )

            # ── P2-FIX-7: GDPR deletion audit log (sole owner) ───────────────
            db.add(GdprDeletionLog(
                org_id=org_id,
                was_sole_owner=True,
                had_stripe_subscription=had_stripe_subscription,
            ))

            # Flush pending mutations so the DELETE doesn't hit FK conflicts.
            await db.flush()
            await db.delete(org)
        else:
            # Other owners exist — just remove this user from the org.
            # The user row itself is anonymized (FIX-1) and will remain with
            # is_active=False. Stripe PII is cleared on the org (FIX-5).
            org.stripe_customer_id = None

            # P2-FIX-6: Anonymize this user's session events within the org.
            await db.execute(
                update(SessionEvent)
                .where(
                    SessionEvent.org_id == org_id,
                    SessionEvent.user_id == user_id,
                )
                .values(user_id=None, request_payload=None, response_payload=None)
            )

            # ── P2-FIX-7: GDPR deletion audit log (non-sole owner) ───────────
            db.add(GdprDeletionLog(
                org_id=org_id,
                was_sole_owner=False,
                had_stripe_subscription=had_stripe_subscription,
            ))

    # ── Step 7: Commit entire transaction atomically ──────────────────────────
    await db.commit()

    _log.info("GDPR deletion completed for user_id=%s org_id=%s", user_id, org_id)

    # ── Step 8: Blocklist the current access token (keep existing behaviour) ──
    if authorization:
        try:
            raw_token = authorization.removeprefix("Bearer ").strip()
            payload = _sec.decode_access_token(raw_token)
            jti: str = payload.get("jti", "")
            exp: int = payload.get("exp", 0)
            if jti:
                now = int(datetime.now(tz=timezone.utc).timestamp())
                ttl = max(exp - now, 1)
                await redis.setex(f"jti_blocklist:{jti}", ttl, "")
        except Exception:
            pass  # best-effort; user is already anonymized and deactivated

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Email verification ────────────────────────────────────────────────────────


@router.post("/send-verification", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Resend verification email")
async def resend_verification(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis=Depends(get_redis),
) -> Response:
    # Rate limit: max 3 resend attempts per IP per 10 minutes — prevents
    # authenticated-but-unverified users from spamming the resend button.
    if redis is not None:
        client_ip = (
            request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
            .split(",")[0]
            .strip()
        )
        rl_key = f"rate_limit:send_verify:{client_ip}"
        count = await redis.incr(rl_key)
        if count == 1:
            await redis.expire(rl_key, 600)  # 10-minute window
        if count > 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again in 10 minutes.",
            )

    if current_user.is_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already verified")

    if redis is not None:
        rate_key = f"resend_verify:{current_user.id}"
        count = await redis.incr(rate_key)
        if count == 1:
            await redis.expire(rate_key, 300)  # 5-minute window
        if count > 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification email requests. Wait 5 minutes.",
            )

    token = _token_serializer.dumps(str(current_user.id), salt="email-verify")
    verify_url = f"{settings.frontend_url}/verify-email?token={token}"
    await send_email_verification(current_user.email, verify_url)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/verify-email", status_code=status.HTTP_200_OK, summary="Verify email address")
async def verify_email(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> dict:
    try:
        user_id = _token_serializer.loads(token, salt="email-verify", max_age=86400)
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification link has expired")
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_verified:
        user.is_verified = True
        await db.commit()
        if redis is not None:
            await redis.delete(f"org_verified:{user.org_id}")
    return {"message": "Email verified successfully"}


@router.get("/confirm-email-change", status_code=status.HTTP_200_OK, summary="Activate a pending email change")
async def confirm_email_change(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        payload = _token_serializer.loads(token, salt="email-change", max_age=86400)
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmation link has expired")
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid confirmation token")

    user_id: str = payload.get("uid", "")
    new_email: str = payload.get("email", "")
    if not user_id or not new_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid confirmation token")

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Guard against the new address being taken by someone else in the meantime
    conflict = await db.scalar(select(User).where(User.email == new_email, User.id != user.id))
    if conflict is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That email is already in use")

    user.email = new_email
    user.is_verified = True
    await db.commit()
    return {"message": "Email address updated successfully"}


# ── Password reset ────────────────────────────────────────────────────────────


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Request password reset email")
async def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> Response:
    # Rate limit: max 3 requests per IP per 10 minutes — prevents email spam
    # abuse that costs money and risks getting the sending domain blacklisted.
    if redis is not None:
        client_ip = (
            request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
            .split(",")[0]
            .strip()
        )
        rl_key = f"rate_limit:forgot_pwd:{client_ip}"
        count = await redis.incr(rl_key)
        if count == 1:
            await redis.expire(rl_key, 600)  # 10-minute window
        if count > 3:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Try again in 10 minutes.",
            )

    result = await db.execute(select(User).where(User.email == body.email, User.is_active.is_(True)))
    user = result.scalar_one_or_none()
    # Always return 204 — never reveal whether the email exists
    if user is not None:
        token = _token_serializer.dumps(str(user.id), salt="pwd-reset")
        reset_url = f"{settings.frontend_url}/reset-password?token={token}"
        await send_password_reset(user.email, reset_url)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Reset password using token")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> Response:
    try:
        user_id = _token_serializer.loads(body.token, salt="pwd-reset", max_age=3600)
    except SignatureExpired:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset link has expired")
    except BadSignature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 8 characters")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.hashed_password = _sec.hash_password(body.new_password)

    # Revoke all refresh tokens — the old password is no longer valid so all
    # existing sessions must be terminated.
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))

    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
