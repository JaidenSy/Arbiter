"""
Arbiter — SQLAlchemy ORM model: OrgMembership.

Source of truth for which organizations a user belongs to and the role they
hold in each.  A user may belong to many orgs.

``users.org_id`` and ``users.role`` remain as a denormalized projection of
the membership the user currently has *active* (their selected org).  The
projection is updated whenever the user switches org, joins, leaves, or is
removed — it is never consulted to decide whether a membership exists.

Plans, quotas, and billing attach to organizations, never to memberships:
adding or removing members has no billing effect.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OrgMembership(Base):
    """
    A user's membership in one organization.

    Columns:
        id:         Auto-generated UUID primary key.
        user_id:    FK → users.id.
        org_id:     FK → organizations.id.
        role:       RBAC role within this org: owner | admin | member.
        created_at: When the user joined the org.
        updated_at: Auto-updated (e.g. on role change).
    """

    __tablename__ = "org_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_org_memberships_user_org"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_org_memberships_role",
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
        index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="member",
        server_default="member",
    )
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

    def __repr__(self) -> str:
        return f"<OrgMembership user={self.user_id} org={self.org_id} role={self.role!r}>"
