# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
Arbiter Auth service.

Handles user registration, login, token refresh, and logout.  Business
logic lives here; HTTP concerns stay in the endpoint layer.

Token strategy:
    - Access token: HS256 JWT, 1-hour lifetime, jti claim for revocation.
    - Refresh token: opaque ``rt_<64-hex>``, 30-day lifetime, SHA-256 hash
      stored in refresh_tokens table, rotated on every use.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db.models.organization import Organization
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.services.org import org_service

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _pre_hash(plain: str) -> str:
    # SHA-256 pre-hash collapses any-length password to 64 hex chars,
    # preventing bcrypt's silent 72-byte truncation.
    return hashlib.sha256(plain.encode()).hexdigest()


# Always run bcrypt even for unknown emails so response time is constant,
# preventing timing-based email enumeration.
_DUMMY_HASH: str = _pwd_context.hash(_pre_hash("arbiter-timing-guard-dummy-value"))


def _hash_password(plain: str) -> str:
    return _pwd_context.hash(_pre_hash(plain))


def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(_pre_hash(plain), hashed)


# ── Public API ────────────────────────────────────────────────────────────────


async def register(
    db: AsyncSession,
    org_name: str,
    email: str,
    password: str,
) -> tuple[User, str, str]:
    """
    Self-serve registration: create org + owner user in one step.

    Args:
        db:        Async database session.
        org_name:  Human-readable name for the new organization.
        email:     Owner's login email.
        password:  Plain-text password (bcrypt-hashed before storage).

    Returns:
        tuple[User, str, str]: (user, access_token, refresh_token)

    Raises:
        HTTPException 409: If the email is already registered.
        HTTPException 409: If the slugified org name is already taken.
    """
    # Validate email uniqueness.
    existing_user = await db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        )

    # Create organization (unique slug handled by the org service).
    org = await org_service.create_org(db, org_name)

    # Create owner user. tos_accepted_at is set immediately since the registration
    # form requires explicit checkbox acceptance before the form can be submitted.
    # users.org_id / users.role are the active-org projection; the membership
    # row below is the source of truth.
    user = User(
        org_id=org.id,
        email=email,
        hashed_password=_hash_password(password),
        role="owner",
        is_active=True,
        tos_accepted_at=datetime.now(UTC),
        tos_version="2026-05-31",
    )
    db.add(user)
    await db.flush()
    await org_service.add_membership(db, user=user, org_id=org.id, role="owner")

    # Issue tokens.
    access_token = security.create_access_token(
        user_id=user.id,
        org_id=org.id,
        role=user.role,
    )
    raw_refresh = security.generate_refresh_token()
    await _store_refresh_token(db, user_id=user.id, raw_token=raw_refresh)

    await db.commit()
    await db.refresh(user)
    return user, access_token, raw_refresh


async def login(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[User, str, str]:
    """
    Authenticate with email/password and issue a new token pair.

    Args:
        db:       Async database session.
        email:    User's login email.
        password: Plain-text password to verify.

    Returns:
        tuple[User, str, str]: (user, access_token, refresh_token)

    Raises:
        HTTPException 401: On invalid credentials, inactive user, or suspended org.
    """
    user = await db.scalar(select(User).where(User.email == email))

    # Always run bcrypt regardless of whether the user exists: prevents
    # timing-based email enumeration (short-circuit would skip the ~100ms hash).
    candidate_hash = user.hashed_password if user is not None else _DUMMY_HASH
    password_ok = _verify_password(password, candidate_hash)

    if not password_ok and user is not None:
        # Legacy hash (no SHA-256 pre-hash): verify and silently re-hash on success.
        if _pwd_context.verify(password, candidate_hash):
            password_ok = True
            user.hashed_password = _hash_password(password)
            await db.flush()

    if not password_ok or user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    org = await db.get(Organization, user.org_id)
    if org is None or not org.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is suspended",
        )

    access_token = security.create_access_token(
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
    )
    raw_refresh = security.generate_refresh_token()
    await _store_refresh_token(db, user_id=user.id, raw_token=raw_refresh)

    await db.commit()
    return user, access_token, raw_refresh


async def refresh_tokens(
    db: AsyncSession,
    redis,
    raw_token: str,
) -> tuple[str, str]:
    """
    Rotate a refresh token: revoke the old one and issue a fresh pair.

    Args:
        db:        Async database session.
        redis:     Redis client (for jti blocklist: not used here directly
                   but available for future expansion).
        raw_token: Raw ``rt_<64-hex>`` token from the client.

    Returns:
        tuple[str, str]: (new_access_token, new_refresh_token)

    Raises:
        HTTPException 401: If the token is not found, revoked, or expired.
    """
    token_hash = security.hash_refresh_token(raw_token)

    rt = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    now = datetime.now(tz=UTC)

    if rt is None or rt.revoked or rt.expires_at.replace(tzinfo=UTC) <= now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revoke the consumed token.
    rt.revoked = True
    await db.flush()

    # Load user for new token claims.
    user = await db.get(User, rt.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue fresh pair.
    new_access = security.create_access_token(
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
    )
    new_raw_refresh = security.generate_refresh_token()
    await _store_refresh_token(db, user_id=user.id, raw_token=new_raw_refresh)

    await db.commit()
    return new_access, new_raw_refresh


async def logout(
    db: AsyncSession,
    redis,
    jti: str,
    exp: int,
    user_id: uuid.UUID,
    all_devices: bool = False,
) -> None:
    """
    Invalidate the current session.

    Adds the JWT's jti to the Redis blocklist so it is rejected immediately
    even before it expires.  Optionally revokes all refresh tokens for the
    user (logout from all devices).

    Args:
        db:         Async database session.
        redis:      Redis client.
        jti:        JWT ID claim from the access token.
        exp:        JWT expiry Unix timestamp.
        user_id:    UUID of the user logging out.
        all_devices: If True, revoke all refresh tokens for the user.
    """
    now = int(datetime.now(tz=UTC).timestamp())
    ttl = max(exp - now, 1)
    await redis.setex(f"jti_blocklist:{jti}", ttl, "")

    if all_devices:
        tokens = (
            await db.scalars(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked.is_(False),
                )
            )
        ).all()
        for token in tokens:
            token.revoked = True
    else:
        # Revoke the single active refresh token associated with this session.
        # Best-effort; no error if already revoked.
        tokens = (
            await db.scalars(
                select(RefreshToken).where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked.is_(False),
                )
            )
        ).all()
        # Revoke the most recently created one (the current session's token).
        if tokens:
            most_recent = max(tokens, key=lambda t: t.created_at)
            most_recent.revoked = True

    await db.commit()


async def create_token_pair(db: AsyncSession, user: User) -> tuple[str, str]:
    """Issue a fresh access + refresh token pair for an already-authenticated user."""
    access_token = security.create_access_token(
        user_id=user.id,
        org_id=user.org_id,
        role=user.role,
    )
    raw_refresh = security.generate_refresh_token()
    await _store_refresh_token(db, user_id=user.id, raw_token=raw_refresh)
    await db.commit()
    return access_token, raw_refresh


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _store_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    raw_token: str,
) -> RefreshToken:
    """
    Persist a hashed refresh token row with a 30-day expiry.

    Args:
        db:        Async database session.
        user_id:   UUID of the owning user.
        raw_token: Plaintext ``rt_<64-hex>`` token.

    Returns:
        RefreshToken: The newly created (unflushed) row.
    """
    from app.core.config import settings

    expires_at = datetime.now(tz=UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    rt = RefreshToken(
        user_id=user_id,
        token_hash=security.hash_refresh_token(raw_token),
        expires_at=expires_at,
        revoked=False,
    )
    db.add(rt)
    await db.flush()
    return rt
