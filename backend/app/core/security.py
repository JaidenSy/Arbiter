"""
NexusAI — Security utilities.

Provides deterministic hashing of API keys for storage and constant-time
comparison for verification.  Raw API keys are NEVER stored in the database;
only their SHA-256 hashes are persisted.

Key lifecycle:
    1. generate_api_key() → returns raw key shown once to the user
    2. hash_api_key(raw)  → stores the hash in agents.api_key_hash
    3. verify_api_key(raw, stored_hash) → used at request time
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_api_key(prefix: str = "nxai") -> str:
    """
    Generate a cryptographically random API key.

    The key is URL-safe and prefixed for easy identification in logs.
    Format: ``<prefix>_<64-char-hex-token>``

    Args:
        prefix: Short string prepended to the key (default ``nxai``).

    Returns:
        str: The raw API key — shown to the user once, never stored.
    """
    # TODO: return f"{prefix}_{secrets.token_hex(32)}"
    raise NotImplementedError("generate_api_key not yet implemented")


def hash_api_key(raw_key: str) -> str:
    """
    Produce a SHA-256 hex digest of a raw API key.

    This digest is stored in the database.  The raw key is never persisted.

    Args:
        raw_key: The plaintext API key returned by generate_api_key().

    Returns:
        str: 64-character hexadecimal SHA-256 digest.
    """
    # TODO: return hashlib.sha256(raw_key.encode()).hexdigest()
    raise NotImplementedError("hash_api_key not yet implemented")


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
    # TODO: computed = hash_api_key(raw_key)
    # TODO: return hmac.compare_digest(computed, stored_hash)
    raise NotImplementedError("verify_api_key not yet implemented")
