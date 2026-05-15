"""
Arbiter — SQLAlchemy ORM model: SocialAccount.

Links a User to an OAuth2 identity from an external provider (Google or GitHub).
A user may have at most one social account per provider.

The (provider, provider_user_id) pair is globally unique — it is the lookup key
used on every SSO login to identify the user without relying on email alone.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class SocialAccount(Base):
    """
    OAuth2 identity linked to a Arbiter user.

    Columns:
        id:               Auto-generated UUID primary key.
        user_id:          FK → users.id.  The linked Arbiter user.
        org_id:           FK → organizations.id.  Denormalised for fast org queries.
        provider:         OAuth2 provider name: "google" | "github".
        provider_user_id: Opaque user identifier returned by the provider (sub / id).
        email:            Email address returned by the provider (may be None).
        name:             Display name returned by the provider (may be None).
        avatar_url:       Profile picture URL from the provider (may be None).
        created_at:       Immutable insert timestamp.
    """

    __tablename__ = "social_accounts"
    __table_args__ = (
        CheckConstraint(
            "provider IN ('google', 'github')",
            name="ck_social_accounts_provider",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="social_accounts")

    def __repr__(self) -> str:
        return (
            f"<SocialAccount provider={self.provider!r} "
            f"provider_user_id={self.provider_user_id!r} "
            f"user_id={self.user_id!r}>"
        )
