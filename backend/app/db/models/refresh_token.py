"""
NexusAI — SQLAlchemy ORM model: RefreshToken.

Opaque 30-day refresh tokens issued alongside JWTs on login/register.
On use the old token is revoked and a new pair is issued (rotation).
Revoked tokens are retained for 7 days for audit, then swept by a cron.

Token format: ``rt_<64-hex>``
Storage:      SHA-256(raw_token) stored in token_hash — raw token never persisted.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class RefreshToken(Base):
    """
    A persisted refresh token record.

    Columns:
        id:          Auto-generated UUID primary key.
        user_id:     FK → users.id.
        token_hash:  SHA-256 of the raw opaque token (never store raw).
        expires_at:  When this token expires (30 days from issuance).
        revoked:     True once this token has been used or the user logged out.
        created_at:  Immutable insert timestamp.
    """

    __tablename__ = "refresh_tokens"

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
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return (
            f"<RefreshToken id={self.id} user_id={self.user_id} revoked={self.revoked}>"
        )
