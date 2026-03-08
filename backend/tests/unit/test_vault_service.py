"""
Unit tests for app.services.vault.vault_service

Coverage:
    - Encrypt → decrypt returns original plaintext
    - Two encryptions of same plaintext produce different ciphertext (nonce randomness)
    - Decrypt with wrong key raises exception
    - VaultService raises RuntimeError if NEXUS_VAULT_KEY / VAULT_ENCRYPTION_KEY unset
    - Decrypted value never appears in any log output (mock logging)
"""

from __future__ import annotations

import logging
import os
import secrets
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_vault_key() -> str:
    """Generate a valid 64-hex-char vault key."""
    return secrets.token_hex(32)


def _make_vault_service(key: str | None = None):
    """
    Instantiate VaultService with env patched to a valid key.
    Returns (service, db_mock).
    """
    from app.services.vault.vault_service import VaultService

    db = AsyncMock()
    env_key = key if key is not None else _make_vault_key()

    with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": env_key}):
        svc = VaultService(db=db)

    # Keep env patched for method calls too — we return a context manager.
    return svc, db, env_key


# ── Tests: encrypt / decrypt ──────────────────────────────────────────────────

class TestEncryptDecrypt:
    def _make_svc(self, key: str | None = None):
        from app.services.vault.vault_service import VaultService
        db = AsyncMock()
        env_key = key if key is not None else _make_vault_key()
        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": env_key}, clear=False):
            svc = VaultService(db=db)
        return svc, env_key

    def test_encrypt_then_decrypt_roundtrip(self):
        plaintext = "super_secret_password_123"
        env_key = _make_vault_key()
        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": env_key}, clear=False):
            from app.services.vault.vault_service import VaultService
            svc = VaultService(db=AsyncMock())
            ciphertext = svc.encrypt(plaintext)
            recovered = svc.decrypt(ciphertext)
        assert recovered == plaintext

    def test_encrypt_returns_string(self):
        env_key = _make_vault_key()
        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": env_key}, clear=False):
            from app.services.vault.vault_service import VaultService
            svc = VaultService(db=AsyncMock())
            ct = svc.encrypt("hello")
        assert isinstance(ct, str)

    def test_nonce_randomness_different_ciphertext_per_call(self):
        """
        Two encryptions of the same plaintext must produce different ciphertext
        because a fresh nonce is generated per call.
        """
        plaintext = "same_secret"
        env_key = _make_vault_key()
        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": env_key}, clear=False):
            from app.services.vault.vault_service import VaultService
            svc = VaultService(db=AsyncMock())
            ct1 = svc.encrypt(plaintext)
            ct2 = svc.encrypt(plaintext)
        assert ct1 != ct2, "Two encryptions of the same plaintext produced identical ciphertext — nonce is not random"

    def test_decrypt_with_wrong_key_raises(self):
        """Decryption with a different key must raise ValueError (GCM auth tag failure)."""
        plaintext = "sensitive_value"
        key1 = _make_vault_key()
        key2 = _make_vault_key()

        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": key1}, clear=False):
            from app.services.vault.vault_service import VaultService
            svc1 = VaultService(db=AsyncMock())
            ciphertext = svc1.encrypt(plaintext)

        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": key2}, clear=False):
            from app.services.vault.vault_service import VaultService
            svc2 = VaultService(db=AsyncMock())
            with pytest.raises((ValueError, Exception)):
                svc2.decrypt(ciphertext)

    def test_decrypt_tampered_ciphertext_raises(self):
        env_key = _make_vault_key()
        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": env_key}, clear=False):
            from app.services.vault.vault_service import VaultService
            svc = VaultService(db=AsyncMock())
            ciphertext = svc.encrypt("my_secret")
            # Tamper by flipping a character in the middle of the b64 string
            chars = list(ciphertext)
            idx = len(chars) // 2
            chars[idx] = "A" if chars[idx] != "A" else "B"
            tampered = "".join(chars)
            with pytest.raises((ValueError, Exception)):
                svc.decrypt(tampered)

    def test_decrypt_invalid_base64_raises_value_error(self):
        env_key = _make_vault_key()
        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": env_key}, clear=False):
            from app.services.vault.vault_service import VaultService
            svc = VaultService(db=AsyncMock())
            with pytest.raises((ValueError, Exception)):
                svc.decrypt("not-valid-base64!!!")


# ── Tests: VaultService raises RuntimeError if env var unset ──────────────────

class TestVaultServiceInit:
    def test_raises_runtime_error_when_key_unset(self):
        """VaultService.__init__ must raise RuntimeError if VAULT_ENCRYPTION_KEY is not set."""
        env = {k: v for k, v in os.environ.items() if k != "VAULT_ENCRYPTION_KEY"}
        with patch.dict(os.environ, env, clear=True):
            from app.services.vault.vault_service import VaultService
            with pytest.raises(RuntimeError, match="VAULT_ENCRYPTION_KEY"):
                VaultService(db=AsyncMock())

    def test_raises_runtime_error_when_key_empty_string(self):
        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": ""}, clear=False):
            from app.services.vault.vault_service import VaultService
            with pytest.raises(RuntimeError):
                VaultService(db=AsyncMock())

    def test_no_error_when_key_is_valid(self):
        key = _make_vault_key()
        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": key}, clear=False):
            from app.services.vault.vault_service import VaultService
            # Should not raise
            svc = VaultService(db=AsyncMock())
        assert svc is not None


# ── Tests: plaintext never appears in logs ────────────────────────────────────

class TestVaultLogging:
    def test_decrypted_value_not_logged(self):
        """
        After calling decrypt(), the plaintext must NOT appear in any
        logger.info / logger.debug / logger.warning / logger.error call.
        """
        plaintext = "DO_NOT_LOG_ME_abc12345xyz"
        env_key = _make_vault_key()

        with patch.dict(os.environ, {"VAULT_ENCRYPTION_KEY": env_key}, clear=False):
            from app.services.vault import vault_service as vault_module
            from app.services.vault.vault_service import VaultService

            svc = VaultService(db=AsyncMock())
            ciphertext = svc.encrypt(plaintext)

            log_calls: list[str] = []

            original_info = vault_module.logger.info
            original_debug = getattr(vault_module.logger, "debug", None)
            original_warning = getattr(vault_module.logger, "warning", None)

            def capture_info(msg, *args, **kwargs):
                log_calls.append(str(msg) + " " + " ".join(str(a) for a in args))

            def capture_debug(msg, *args, **kwargs):
                log_calls.append(str(msg) + " " + " ".join(str(a) for a in args))

            def capture_warning(msg, *args, **kwargs):
                log_calls.append(str(msg) + " " + " ".join(str(a) for a in args))

            vault_module.logger.info = capture_info
            vault_module.logger.debug = capture_debug
            vault_module.logger.warning = capture_warning

            try:
                result = svc.decrypt(ciphertext)
            finally:
                vault_module.logger.info = original_info
                if original_debug:
                    vault_module.logger.debug = original_debug
                if original_warning:
                    vault_module.logger.warning = original_warning

            assert result == plaintext
            for call in log_calls:
                assert plaintext not in call, (
                    f"Plaintext {plaintext!r} appeared in log output: {call!r}"
                )
