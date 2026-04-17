"""
Nexvault — Application configuration.

All settings are read from environment variables (or a .env file when
APP_ENV=development). No secrets are hardcoded here — see .env.example.

Uses pydantic-settings so every field is type-validated at startup.
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings class.  Populated from environment variables.

    Priority order (highest → lowest):
        1. Shell environment variables
        2. .env file (development only)
        3. Field default values
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_env: str = "development"
    app_debug: bool = False
    app_secret_key: str  # required — no default

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str  # required — asyncpg DSN

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str  # required — redis:// DSN

    # ── Vault / Encryption ────────────────────────────────────────────────────
    vault_encryption_key: str  # required — 64-char hex (AES-256)

    # ── Semantic Cache ────────────────────────────────────────────────────────
    cache_embedding_model: str = "all-MiniLM-L6-v2"
    cache_similarity_threshold: float = 0.95
    cache_ttl_seconds: int = 3600

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_secret_key: str = "nexvault_dev_jwt_secret_change_in_production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 1440  # 24 hours
    jwt_refresh_token_expire_days: int = 30

    # ── Registration ──────────────────────────────────────────────────────────
    allow_public_registration: bool = True
    # When allow_public_registration=False, users may still register if they
    # supply this code. Leave empty to fully disable self-serve registration.
    invite_code: str = ""

    # ── Quota ─────────────────────────────────────────────────────────────────
    quota_cache_ttl_seconds: int = 60

    # ── OAuth2 Social Login ────────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    oauth_redirect_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"

    # ── Stripe ────────────────────────────────────────────────────────────────
    stripe_secret_key: str = ""       # required in production — sk_live_... or sk_test_...
    stripe_webhook_secret: str = ""   # required — whsec_... from Stripe dashboard or CLI
    stripe_pro_price_id: str = ""     # required — price_... from Stripe product catalog

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """Accept comma-separated string or list from env."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",")]
        return value

    @field_validator("vault_encryption_key")
    @classmethod
    def validate_encryption_key(cls, value: str) -> str:
        """Ensure key is exactly 64 hex characters (256-bit AES key)."""
        if len(value) != 64:
            raise ValueError(
                "VAULT_ENCRYPTION_KEY must be 64 hex characters (256-bit / 32 bytes)"
            )
        return value

    @property
    def is_production(self) -> bool:
        """True when APP_ENV=production."""
        return self.app_env.lower() == "production"


settings = Settings()  # type: ignore[call-arg]
