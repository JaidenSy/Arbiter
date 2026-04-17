"""
NexVault — SQLAlchemy ORM model: User.

A User represents a human operator who logs in to the dashboard with an
email/password and receives a JWT.  Users are NOT the same as Agents;
agents are programmatic API-key callers, users are human operators.

Role semantics:
    owner  — full org control: delete org, manage billing, promote/demote admins.
             Minimum one owner per org (enforced at app layer).
    admin  — create/delete agents, MCP servers, vault secrets, manage members.
    member — read-only dashboard access; cannot mutate resources.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.organization import Organization
    from app.db.models.refresh_token import RefreshToken
    from app.db.models.social_account import SocialAccount


class User(Base):
    """
    Human operator with email/password credentials.

    Columns:
        id:              Auto-generated UUID primary key.
        org_id:          FK → organizations.id.  Users belong to exactly one org.
        email:           Unique login email address.
        hashed_password: bcrypt hash (cost factor 12).  Raw password never stored.
        role:            RBAC role within the org: owner | admin | member.
        is_active:       Soft-delete; inactive users cannot log in.
        created_at:      Immutable insert timestamp.
        updated_at:      Auto-updated on every modification.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_users_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(72), nullable=False, default="")
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="member",
        server_default="member",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    org: Mapped["Organization"] = relationship("Organization", back_populates="users")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    social_accounts: Mapped[list["SocialAccount"]] = relationship(
        "SocialAccount",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
