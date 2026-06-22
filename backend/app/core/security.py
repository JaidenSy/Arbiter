# Copyright 2026 Jaiden Sy
# SPDX-License-Identifier: Apache-2.0
"""
Arbiter Security utilities.

Provides deterministic hashing of API keys for storage and constant-time
comparison for verification.  Raw API keys are NEVER stored in the database;
only their SHA-256 hashes are persisted.

Key lifecycle:
    1. generate_api_key() → returns raw key shown once to the user
    2. hash_api_key(raw)  → stores the hash in agents.api_key_hash
    3. verify_api_key(raw, stored_hash) → used at request time

Also provides JWT creation/decoding and refresh token helpers for the
human-operator auth flow (email/password → JWT + opaque refresh token).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext

from app.core.config import settings

# Shared bcrypt context used for user password hashing/verification.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_api_key(prefix: str = "nxai") -> str:
    """
    Generate a cryptographically random API key.

    The key is URL-safe and prefixed for easy identification in logs.
    Format: ``<prefix>_<64-char-hex-token>``

    Args:
        prefix: Short string prepended to the key (default ``nxai``).

    Returns:
        str: The raw API key: shown to the user once, never stored.
    """
    return f"{prefix}_{secrets.token_hex(32)}"


def hash_api_key(raw_key: str) -> str:
    """
    Produce a SHA-256 hex digest of a raw API key.

    This digest is stored in the database.  The raw key is never persisted.

    Args:
        raw_key: The plaintext API key returned by generate_api_key().

    Returns:
        str: 64-character hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(raw_key.encode()).hexdigest()


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """
    Constant-time comparison of a raw key against its stored hash.

    Uses ``hmac.compare_digest`` to prevent timing attacks.

    Args:
        raw_key: The plaintext key provided by the caller.
        stored_hash: The SHA-256 hex digest stored in the database.

    Returns:
        bool: True if the key matches, False otherwise.
    """
    computed = hash_api_key(raw_key)
    return hmac.compare_digest(computed, stored_hash)


# ── Password helpers ─────────────────────────────────────────────────────────


def _pre_hash(plain: str) -> str:
    # SHA-256 pre-hash collapses any-length password to 64 hex chars,
    # preventing bcrypt's silent 72-byte truncation.
    return hashlib.sha256(plain.encode()).hexdigest()


def hash_password(plain: str) -> str:
    """
    Bcrypt-hash a plaintext password for storage.

    Args:
        plain: The user's plaintext password.

    Returns:
        str: A bcrypt hash string safe to store in the database.
    """
    return pwd_context.hash(_pre_hash(plain))


def verify_password(plain: str, hashed: str) -> bool:
    """
    Constant-time bcrypt verification of a plaintext password.

    Args:
        plain:  The plaintext password provided by the user.
        hashed: The bcrypt hash stored in the database.

    Returns:
        bool: True if the password matches, False otherwise.
    """
    return pwd_context.verify(_pre_hash(plain), hashed)


def verify_password_legacy(plain: str, hashed: str) -> bool:
    """Verify against a pre-migration hash (no SHA-256 pre-hash). Migration use only."""
    return pwd_context.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────


def create_access_token(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    role: str,
) -> str:
    """
    Issue a signed HS256 access token.

    Payload claims:
        sub    : user UUID (string)
        org_id : org UUID (string)
        role   : RBAC role within the org
        type   : "access" (distinguishes from future service tokens)
        jti    : unique token ID enabling Redis-based revocation
        iat    : issued-at (UTC)
        exp    : expiry (UTC)

    Args:
        user_id: UUID of the authenticated user.
        org_id:  UUID of the user's organization.
        role:    RBAC role string (owner | admin | member).

    Returns:
        str: Signed JWT string.
    """
    now = datetime.now(tz=UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_cli_access_token(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    role: str,
    expire_minutes: int,
) -> str:
    """
    Issue a signed HS256 access token for CLI device-flow sessions.

    Identical payload structure to create_access_token but accepts an explicit
    TTL so the caller (cli_auth endpoint) can use cli_token_expire_minutes from
    settings without modifying the shared helper.

    Args:
        user_id:        UUID of the authenticated user.
        org_id:         UUID of the user's organization.
        role:           RBAC role string (owner | admin | member).
        expire_minutes: Token lifetime in minutes.

    Returns:
        str: Signed JWT string.
    """
    now = datetime.now(tz=UTC)
    expire = now + timedelta(minutes=expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "org_id": str(org_id),
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT access token.

    Args:
        token: Raw JWT string from the Authorization header.

    Returns:
        dict: Verified payload claims.

    Raises:
        HTTPException 401: On invalid signature, expiry, or malformed token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ── Refresh token helpers ─────────────────────────────────────────────────────


def generate_refresh_token() -> str:
    """
    Generate a cryptographically random opaque refresh token.

    Format: ``rt_<64-char-hex>``

    Returns:
        str: Raw refresh token: shown to the caller, never stored directly.
    """
    return f"rt_{secrets.token_hex(32)}"


def hash_refresh_token(raw: str) -> str:
    """
    Produce a SHA-256 hex digest of a raw refresh token.

    The digest is stored in refresh_tokens.token_hash.  The raw token
    is never persisted.

    Args:
        raw: The plaintext refresh token.

    Returns:
        str: 64-character hexadecimal SHA-256 digest.
    """
    return hashlib.sha256(raw.encode()).hexdigest()
