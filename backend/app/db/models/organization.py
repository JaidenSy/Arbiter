"""
Arbiter — SQLAlchemy ORM model: Organization.

An Organization is the top-level multi-tenancy boundary.  All resources
(agents, MCP servers, vault secrets, sessions) belong to exactly one org.
Users are human operators scoped to an org; agents are programmatic callers.

Plan tiers map to hard resource limits enforced at the service layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class Organization(Base):
    """
    A tenant organization in the Arbiter gateway.

    Columns:
        id:                    Auto-generated UUID primary key.
        name:                  Human-readable org name (e.g. "Acme Corp").
        slug:                  URL-safe unique identifier (e.g. "acme-corp").
        plan_tier:             Determines resource limits: free | pro | enterprise.
        is_active:             Soft-delete / suspension flag.
        stripe_customer_id:    Stripe customer ID — NULL until billing is activated.
        stripe_subscription_id: Stripe subscription ID — NULL until billing is activated.
        created_at:            Immutable insert timestamp.
        updated_at:            Auto-updated on every modification.
    """

    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "plan_tier IN ('free', 'pro', 'enterprise')",
            name="ck_organizations_plan_tier",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    plan_tier: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="free",
        server_default="free",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    quota_alert_80_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    quota_alert_100_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="org",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Organization id={self.id} slug={self.slug!r} plan={self.plan_tier!r}>"
        )
