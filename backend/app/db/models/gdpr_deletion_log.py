"""
Arbiter SQLAlchemy ORM model: GdprDeletionLog.

Records a non-PII audit entry every time a user exercises their GDPR
Art.17 right to erasure.  No personal data is stored here: the sole
purpose is to provide an internal audit trail that an erasure was
processed and whether it involved a sole owner or an active Stripe
subscription.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GdprDeletionLog(Base):
    """
    Non-PII audit record of a GDPR Art.17 deletion request.

    Columns:
        id:                       UUID primary key.
        deleted_at:               When the deletion was processed (indexed).
        org_id:                   UUID of the org at deletion time: nullable
                                  because the org itself may have been deleted.
                                  Stored for internal auditing only; no PII.
        was_sole_owner:           True when the deleting user was the last owner,
                                  causing the entire org to be torn down.
        had_stripe_subscription:  True when an active Stripe subscription existed
                                  at the time of deletion (already cancelled by
                                  the time this row is written).
    """

    __tablename__ = "gdpr_deletion_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    was_sole_owner: Mapped[bool] = mapped_column(Boolean, nullable=False)
    had_stripe_subscription: Mapped[bool] = mapped_column(Boolean, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<GdprDeletionLog id={self.id} deleted_at={self.deleted_at} "
            f"was_sole_owner={self.was_sole_owner}>"
        )
