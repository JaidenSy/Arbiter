"""
Arbiter — SQLAlchemy ORM model: VaultAuditEvent.

Immutable structured audit trail for vault secret lifecycle operations.
One row is written per operation (create, read/reveal, delete, rotate).

NOTE: This model requires a corresponding Alembic migration before it can
be used against a live database.  The migration has not been included in
this PR — see PR description for details.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VaultOperation(str, enum.Enum):
    """The vault operation being audited."""

    create = "create"
    read = "read"
    delete = "delete"
    rotate = "rotate"


class VaultAuditEvent(Base):
    """
    Immutable audit record for a vault secret operation.

    Columns:
        id:         UUID primary key.
        org_id:     FK → organizations.id (denormalized for org-scoped queries).
        secret_id:  FK → vault_secrets.id (nullable — secret may be deleted).
        user_id:    FK → users.id — the user who triggered the operation.
        operation:  Enum — create / read / delete / rotate.
        timestamp:  When the operation occurred (server-set, immutable).
    """

    __tablename__ = "vault_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    secret_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vault_secrets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operation: Mapped[VaultOperation] = mapped_column(
        Enum(VaultOperation, name="vault_operation"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<VaultAuditEvent op={self.operation!r} "
            f"secret_id={self.secret_id} user_id={self.user_id}>"
        )
