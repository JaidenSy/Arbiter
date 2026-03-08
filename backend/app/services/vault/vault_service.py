"""
NexusAI — VaultService.

Provides AES-256-GCM encryption/decryption and CRUD operations for secrets
stored in the vault_secrets table.

Design decisions:
    - AES-256-GCM chosen for authenticated encryption (prevents tampering).
    - Nonce (96-bit / 12-byte random) is prepended to the ciphertext before
      Base64 encoding; the GCM auth tag is appended by the AESGCM primitive.
    - The raw encryption key is read from VAULT_ENCRYPTION_KEY (64 hex chars
      → 32 bytes).
    - Database stores ciphertext only; the key never touches the DB.
    - Decrypted values are NEVER logged.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import uuid

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.vault import VaultSecret

logger = logging.getLogger(__name__)

# ── Key derivation ─────────────────────────────────────────────────────────────

def _load_key() -> bytes:
    """
    Derive the 32-byte AES-256 key from the VAULT_ENCRYPTION_KEY env var.

    The env var is expected to be a 64-hex-char string (validated by
    pydantic-settings at startup).  We SHA-256 hash it defensively in case
    the user supplies something that is hex but not exactly 32 bytes after
    decoding (the config validator already enforces 64 chars, so this is
    belt-and-suspenders).

    Raises:
        RuntimeError: If VAULT_ENCRYPTION_KEY is not set.
    """
    raw = os.environ.get("VAULT_ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError(
            "VAULT_ENCRYPTION_KEY environment variable is not set. "
            "The application cannot start without it."
        )
    # Hex-decode 64 chars → 32 bytes, then SHA-256 to normalise length.
    try:
        key_bytes = bytes.fromhex(raw)
    except ValueError as exc:
        raise RuntimeError(
            f"VAULT_ENCRYPTION_KEY is not valid hex: {exc}"
        ) from exc
    # key_bytes should be 32 bytes; SHA-256 ensures exactly 32 regardless.
    return hashlib.sha256(key_bytes).digest()


class VaultService:
    """
    Handles encryption, decryption, and persistence of secrets.

    All methods are async to allow non-blocking DB access.  Encryption is
    CPU-bound but fast enough that it does not require a thread pool for
    typical secret sizes.
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialise the service with an injected DB session.

        Loads the encryption key from the environment on every instantiation.
        The key is never stored as an instance attribute beyond the scope of
        a method call — it exists only transiently in _load_key().

        Args:
            db: Async SQLAlchemy session bound to the current request.

        Raises:
            RuntimeError: If VAULT_ENCRYPTION_KEY is not set.
        """
        self.db = db
        # Validate key is available at construction time; fail fast.
        _load_key()

    # ── Encryption primitives ─────────────────────────────────────────────────

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string using AES-256-GCM.

        A fresh 96-bit (12-byte) nonce is generated for every call.
        AESGCM appends a 16-byte auth tag to the ciphertext automatically.
        The result is ``base64(nonce + ciphertext+tag)``.

        Args:
            plaintext: The raw secret value to protect.

        Returns:
            str: Base64-encoded nonce+ciphertext+tag string, safe for DB
                 storage as TEXT.
        """
        key = _load_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)  # 96-bit nonce per NIST SP 800-38D
        ct_with_tag = aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ct_with_tag).decode()

    def decrypt(self, ciphertext_b64: str) -> str:
        """
        Decrypt a Base64-encoded AES-256-GCM ciphertext.

        Args:
            ciphertext_b64: Value previously returned by encrypt().

        Returns:
            str: The original plaintext secret.

        Raises:
            ValueError: If the ciphertext has been tampered with (GCM tag
                        check fails) or the Base64 is malformed.
        """
        key = _load_key()
        aesgcm = AESGCM(key)
        try:
            raw = base64.b64decode(ciphertext_b64)
        except Exception as exc:
            raise ValueError(f"Ciphertext is not valid Base64: {exc}") from exc

        nonce = raw[:12]
        ct_with_tag = raw[12:]
        try:
            plaintext_bytes = aesgcm.decrypt(nonce, ct_with_tag, None)
        except Exception as exc:
            # Do NOT include ciphertext details in the error — they could leak
            # information about partial decryption state.
            raise ValueError("Decryption failed: ciphertext may be tampered") from exc

        return plaintext_bytes.decode()

    # ── Persistence ───────────────────────────────────────────────────────────

    async def store_secret(
        self,
        name: str,
        plaintext: str,
        agent_id: uuid.UUID | None = None,
    ) -> VaultSecret:
        """
        Encrypt and persist a secret.

        If a secret with the same name already exists it is updated (upsert /
        key rotation).  The plaintext is encrypted immediately and the raw
        value is not retained after this method returns.

        Args:
            name:      Logical key (e.g. "GITHUB_TOKEN").
            plaintext: Raw secret value — never stored.
            agent_id:  Optional owner agent UUID.

        Returns:
            VaultSecret: The persisted ORM row (ciphertext only, no plaintext).
        """
        ciphertext = self.encrypt(plaintext)

        # Scope upsert to (name, agent_id) — prevents cross-agent secret collision.
        result = await self.db.execute(
            select(VaultSecret).where(
                VaultSecret.name == name,
                VaultSecret.agent_id == agent_id,
            )
        )
        secret = result.scalar_one_or_none()

        if secret is None:
            secret = VaultSecret(
                name=name,
                ciphertext=ciphertext,
                agent_id=agent_id,
            )
            self.db.add(secret)
        else:
            secret.ciphertext = ciphertext
            if agent_id is not None:
                secret.agent_id = agent_id

        await self.db.commit()
        await self.db.refresh(secret)

        logger.info("vault: stored secret name=%r agent_id=%s", name, agent_id)
        return secret

    async def get_secret(self, name: str) -> str:
        """
        Retrieve and decrypt a secret by logical name.

        SECURITY: The decrypted value is NEVER logged.

        Args:
            name: Logical key used when storing the secret.

        Returns:
            str: Decrypted plaintext secret.

        Raises:
            KeyError: If no secret with the given name exists.
        """
        result = await self.db.execute(
            select(VaultSecret).where(VaultSecret.name == name)
        )
        secret = result.scalar_one_or_none()

        if secret is None:
            raise KeyError(f"Secret not found: {name!r}")

        logger.info("vault: accessed secret name=%r", name)
        # Decrypt — never log the return value.
        return self.decrypt(secret.ciphertext)
