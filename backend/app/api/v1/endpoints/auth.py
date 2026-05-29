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

from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
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
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenResponse:
    if redis is not None:
        rate_key = f"login_attempts:{body.email}"
        attempts = await redis.incr(rate_key)
        if attempts == 1:
            await redis.expire(rate_key, 900)  # 15-minute window
        if attempts > 10:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again in 15 minutes.",
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    from passlib.context import CryptContext
    _pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

    if not current_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses SSO — password change is not available",
        )

    if not _pwd.verify(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = _pwd.hash(body.new_password)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate account and revoke all sessions",
)
async def delete_me(
    authorization: str | None = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> Response:
    # Soft-delete the user
    current_user.is_active = False

    # Revoke all refresh tokens
    tokens = (
        await db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == current_user.id,
                RefreshToken.revoked.is_(False),
            )
        )
    ).all()
    for token in tokens:
        token.revoked = True

    await db.commit()

    # Blocklist the current access token
    if authorization:
        try:
            raw_token = authorization.removeprefix("Bearer ").strip()
            payload = _sec.decode_access_token(raw_token)
            jti: str = payload.get("jti", "")
            exp: int = payload.get("exp", 0)
            if jti:
                from datetime import datetime, timezone
                now = int(datetime.now(tz=timezone.utc).timestamp())
                ttl = max(exp - now, 1)
                await redis.setex(f"jti_blocklist:{jti}", ttl, "")
        except Exception:
            pass  # best-effort; user is already deactivated

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Email verification ────────────────────────────────────────────────────────


@router.post("/send-verification", status_code=status.HTTP_204_NO_CONTENT, response_model=None, summary="Resend verification email")
async def resend_verification(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis=Depends(get_redis),
) -> Response:
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
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
