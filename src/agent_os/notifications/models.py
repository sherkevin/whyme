"""PRD10 ``Notification`` ORM table (§5.16 / §15)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from agent_os.db.base import Base


class NotificationType(str, enum.Enum):
    """Loose enum reflecting PRD10 §5.16 examples.

    Stored as a free-form string column so domains can extend without a
    migration; the enum here documents the canonical types PRD10 mentions.
    """

    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    INSIGHT_GENERATED = "insight_generated"
    DOCUMENT_READY = "document_ready"
    UPLOAD_FAILED = "upload_failed"
    AI_OUTPUT_SAVED = "ai_output_saved"
    SKILL_RUN_COMPLETED = "skill_run_completed"
    SYSTEM = "system"


class Notification(Base):
    """User-facing notification.

    PRD10 §15 lets the UI poll for unread count and mark items read; the
    field set here matches §5.16.
    """

    __tablename__ = "prd10_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    type = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)

    object_type = Column(String(50), nullable=True, index=True)
    object_id = Column(String(64), nullable=True)

    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index(
            'idx_prd10_notifications_user_read_created',
            'user_id', 'is_read', 'created_at',
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, user_id={self.user_id}, "
            f"type={self.type}, is_read={self.is_read})>"
        )

    def to_prd10_dict(self) -> dict:
        """Serialize to PRD10 §5.16 notification DTO."""

        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "type": self.type,
            "title": self.title,
            "content": self.content,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
