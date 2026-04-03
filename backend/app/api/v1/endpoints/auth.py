"""
NexusAI — API endpoints: Auth.

Human-operator authentication via email/password + JWT + rotating refresh tokens.

Routes:
    POST /auth/register  → 201  issue tokens for new org + owner
    POST /auth/login     → 200  issue tokens for existing user
    POST /auth/refresh   → 200  rotate refresh token, issue fresh pair
    POST /auth/logout    → 204  invalidate access token; optionally all devices
    GET  /auth/me        → 200  current user profile
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security as _sec
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db, get_redis
from app.db.models.organization import Organization
from app.db.models.user import User
from app.schemas.auth import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.auth import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new organization and owner account",
)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Self-serve registration.

    Creates a new organization (plan=free) and an owner user in a single
    atomic transaction, then returns a token pair so the caller is
    immediately authenticated.

    Args:
        body: org_name, email, and password.
        db:   Injected database session.

    Returns:
        TokenResponse: access_token, refresh_token, token_type, expires_in.

    Raises:
        HTTPException 403: If public registration is disabled by config.
        HTTPException 409: If the email is already in use.
    """
    if not settings.allow_public_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is disabled",
        )

    _user, access_token, refresh_token = await auth_service.register(
        db=db,
        org_name=body.org_name,
        email=body.email,
        password=body.password,
    )

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
) -> TokenResponse:
    """
    Email/password login.

    Args:
        body: email and password.
        db:   Injected database session.

    Returns:
        TokenResponse: access_token, refresh_token, token_type, expires_in.

    Raises:
        HTTPException 401: On invalid credentials or inactive account.
        HTTPException 403: If the org is suspended.
    """
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
    """
    Token rotation.

    Validates the presented refresh token, revokes it, and issues a new
    access token + refresh token pair (one-time-use rotation).

    Args:
        body:  refresh_token string.
        db:    Injected database session.
        redis: Injected Redis client.

    Returns:
        TokenResponse: Fresh access_token, refresh_token, token_type, expires_in.

    Raises:
        HTTPException 401: If the token is invalid, revoked, or expired.
    """
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
    """
    Log out the current user.

    Adds the JWT's jti to the Redis blocklist so it cannot be reused even
    within its remaining lifetime.  Optionally revokes all refresh tokens.

    Args:
        all_devices:   Revoke all sessions when True (query param ``?all=true``).
        authorization: Raw Authorization header — used to re-extract jti/exp.
        current_user:  Injected authenticated user.
        db:            Injected database session.
        redis:         Injected Redis client.

    Returns:
        204 No Content.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    token = authorization.removeprefix("Bearer ").strip()
    payload = _sec.decode_access_token(token)

    jti: str = payload.get("jti", "")
    exp: int = payload.get("exp", 0)

    await auth_service.logout(
        db=db,
        redis=redis,
        jti=jti,
        exp=exp,
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
    """
    Return profile information for the authenticated user.

    Args:
        current_user: Injected authenticated user.
        db:           Injected database session.

    Returns:
        MeResponse: User ID, email, role, org_id, org name, and plan tier.
    """
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Organization not found",
        )

    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        org_id=current_user.org_id,
        org_name=org.name,
        org_plan=org.plan_tier,
    )
