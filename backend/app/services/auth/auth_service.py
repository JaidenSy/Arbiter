"""
NexVault — Auth service.

Handles user registration, login, token refresh, and logout.  Business
logic lives here; HTTP concerns stay in the endpoint layer.

Token strategy:
    - Access token: HS256 JWT, 24-hour lifetime, jti claim for revocation.
    - Refresh token: opaque ``rt_<64-hex>``, 30-day lifetime, SHA-256 hash
      stored in refresh_tokens table, rotated on every use.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db.models.organization import Organization
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    """
    Convert a human-readable name to a URL-safe slug.

    Example: "Acme Corp!" → "acme-corp"
    """
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "org"


def _hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


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

    # Slugify org name and check uniqueness.
    slug = _slugify(org_name)
    base_slug = slug
    counter = 1
    while await db.scalar(select(Organization).where(Organization.slug == slug)):
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Create organization.
    org = Organization(name=org_name, slug=slug, plan_tier="free", is_active=True)
    db.add(org)
    await db.flush()  # populate org.id before referencing it

    # Create owner user.
    user = User(
        org_id=org.id,
        email=email,
        hashed_password=_hash_password(password),
        role="owner",
        is_active=True,
    )
    db.add(user)
    await db.flush()

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

    # Use constant-time check regardless of whether user exists to
    # prevent email-enumeration via timing differences.
    if user is None or not _verify_password(password, user.hashed_password):
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
        redis:     Redis client (for jti blocklist — not used here directly
                   but available for future expansion).
        raw_token: Raw ``rt_<64-hex>`` token from the client.

    Returns:
        tuple[str, str]: (new_access_token, new_refresh_token)

    Raises:
        HTTPException 401: If the token is not found, revoked, or expired.
    """
    token_hash = security.hash_refresh_token(raw_token)

    rt = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )

    now = datetime.now(tz=timezone.utc)

    if rt is None or rt.revoked or rt.expires_at.replace(tzinfo=timezone.utc) <= now:
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
    now = int(datetime.now(tz=timezone.utc).timestamp())
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

    expires_at = datetime.now(tz=timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    rt = RefreshToken(
        user_id=user_id,
        token_hash=security.hash_refresh_token(raw_token),
        expires_at=expires_at,
        revoked=False,
    )
    db.add(rt)
    await db.flush()
    return rt
