"""
Arbiter SSO service.

Handles the user-provisioning side of OAuth2 social login:

    - get_or_create_user:     Look up / create User + SocialAccount after a
                              successful OAuth2 callback.
    - issue_one_time_token:   Generate a short-lived Redis-backed token to pass
                              back to the frontend via a redirect URL parameter.
    - exchange_one_time_token: Validate and consume the OTT; return a full JWT
                               + refresh token pair.

The one-time-token (OTT) pattern avoids embedding a long-lived JWT in a redirect
URL (which would appear in server logs and browser history).
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db.models.social_account import SocialAccount
from app.db.models.user import User
from app.services.auth.auth_service import _store_refresh_token
from app.services.org import org_service

# Redis key prefix for one-time tokens
_OTT_PREFIX = "ott:"
# TTL in seconds
_OTT_TTL = 60


# ── Public API ────────────────────────────────────────────────────────────────


async def get_or_create_user(
    db: AsyncSession,
    provider: str,
    provider_user_id: str,
    email: str,
    name: str,
    avatar_url: str | None,
) -> User:
    """
    Resolve a social login to a Arbiter User, creating records as needed.

    Lookup order:
        1. Find existing SocialAccount by (provider, provider_user_id).
           If found: return the linked user: no writes.
        2. Find existing User by email (email-linking for accounts that
           registered via email/password first).
           If found: create a new SocialAccount linked to that user.
        3. Neither exists: create a new Organization + User (role=owner)
           + SocialAccount in one transaction.

    Args:
        db:               Async database session.
        provider:         "google" or "github".
        provider_user_id: Stable identifier from the OAuth2 provider.
        email:            Verified email address from the provider.
        name:             Display name from the provider.
        avatar_url:       Profile picture URL (may be None).

    Returns:
        User: The existing or newly-created user.
    """
    # 1. Look up existing social account.
    existing_sa = await db.scalar(
        select(SocialAccount).where(
            SocialAccount.provider == provider,
            SocialAccount.provider_user_id == provider_user_id,
        )
    )
    if existing_sa is not None:
        user = await db.get(User, existing_sa.user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
            )
        return user

    # 2. Check if a user already exists with this email.
    existing_user = await db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        if not existing_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is deactivated",
            )
        # OAuth provider has verified this email: mark the user as verified.
        if not existing_user.is_verified:
            existing_user.is_verified = True
        sa = SocialAccount(
            user_id=existing_user.id,
            org_id=existing_user.org_id,
            provider=provider,
            provider_user_id=provider_user_id,
            email=email,
            name=name,
            avatar_url=avatar_url,
        )
        db.add(sa)
        await db.commit()
        return existing_user

    # 3. Brand-new user: create org + user + membership + social account.
    display_name = name or email.split("@")[0]
    org = await org_service.create_org(db, display_name)

    user = User(
        org_id=org.id,
        email=email,
        hashed_password="",  # SSO-only account: no password login
        role="owner",
        is_active=True,
        is_verified=True,  # OAuth provider verified the email: no additional step needed
    )
    db.add(user)
    await db.flush()
    await org_service.add_membership(db, user=user, org_id=org.id, role="owner")

    sa = SocialAccount(
        user_id=user.id,
        org_id=org.id,
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
    )
    db.add(sa)
    await db.commit()
    await db.refresh(user)
    return user


async def link_provider(
    redis,
    db: AsyncSession,
    nonce: str,
    provider: str,
    provider_user_id: str,
    email: str,
    name: str,
    avatar_url: str | None,
) -> None:
    """
    Link an OAuth provider to an existing user identified by a Redis nonce.

    The nonce was stored by POST /auth/sso/link/initiate and proves the link
    was initiated by an authenticated user. Single-use: deleted on consumption.

    Raises:
        HTTPException 400: Invalid/expired nonce, provider already linked elsewhere,
                           or this user already has this provider linked.
    """
    from app.db.models.social_account import SocialAccount

    nonce_key = f"link_intent:{nonce}"
    user_id_bytes = await redis.get(nonce_key)
    if user_id_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Link session expired. Please try again",
        )
    await redis.delete(nonce_key)

    user_id_str = (
        user_id_bytes.decode("utf-8") if isinstance(user_id_bytes, bytes) else user_id_bytes
    )
    import uuid as _uuid

    user = await db.get(User, _uuid.UUID(user_id_str))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")

    # Check the provider_user_id isn't already claimed by a different account
    existing_sa = await db.scalar(
        select(SocialAccount).where(
            SocialAccount.provider == provider,
            SocialAccount.provider_user_id == provider_user_id,
        )
    )
    if existing_sa is not None and existing_sa.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This {provider} account is already linked to a different user",
        )
    if existing_sa is not None:
        # Already linked to this user: nothing to do
        return

    sa = SocialAccount(
        user_id=user.id,
        org_id=user.org_id,
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
        name=name,
        avatar_url=avatar_url,
    )
    db.add(sa)
    await db.commit()


async def issue_one_time_token(redis, user_id: str) -> str:
    """
    Generate a short-lived one-time token and store the user_id in Redis.

    Format: ``ott_<32-char-hex>``
    Redis key: ``ott:<token>``  →  value: user_id (str), TTL: 60 seconds.

    Args:
        redis:   Redis client (from app.state.redis).
        user_id: String representation of the user UUID.

    Returns:
        str: The raw one-time token (without the ``ott_`` prefix stripped).
    """
    raw = f"ott_{secrets.token_hex(16)}"
    await redis.setex(f"{_OTT_PREFIX}{raw}", _OTT_TTL, user_id)
    return raw


async def exchange_one_time_token(
    redis,
    db: AsyncSession,
    raw_token: str,
) -> tuple[User, str, str]:
    """
    Validate and consume a one-time token; return a full JWT + refresh token.

    The token is deleted from Redis on first use (single-use guarantee).

    Args:
        redis:     Redis client.
        db:        Async database session.
        raw_token: The ``ott_<hex>`` token from the query parameter.

    Returns:
        tuple[User, str, str]: (user, access_token, refresh_token)

    Raises:
        HTTPException 400: If the token is not found, expired, or already used.
        HTTPException 401: If the linked user is inactive.
    """
    redis_key = f"{_OTT_PREFIX}{raw_token}"
    user_id_bytes = await redis.get(redis_key)

    if user_id_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    # Single-use: delete immediately after retrieval.
    await redis.delete(redis_key)

    user_id_str = (
        user_id_bytes.decode("utf-8") if isinstance(user_id_bytes, bytes) else user_id_bytes
    )

    import uuid

    user = await db.get(User, uuid.UUID(user_id_str))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or not found",
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
