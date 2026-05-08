"""PRD10 §5.3 InboxItem table.

The legacy ``inbox/router.py`` re-uses the PRD4 ``items.Item`` model and is kept
for back-compat. PRD10's InboxItem has dedicated fields (``processing_status``,
``priority``, ``source_id``, ``target_folder_id``, ``auto_process``) that don't
fit cleanly on ``Item``, so this module owns the canonical PRD10 table.

All PRD10 Capture endpoints write through ``Prd10InboxItem``.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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


class InboxItemType(str, enum.Enum):
    """PRD10 §5.3 ``type`` enum."""

    TEXT = "text"
    LINK = "link"
    FILE = "file"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    MANUAL_TASK = "manual_task"


class InboxItemStatus(str, enum.Enum):
    """PRD10 §5.3 ``status`` enum."""

    DRAFT = "draft"
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    ARCHIVED = "archived"
    FAILED = "failed"


class InboxItemProcessingStatus(str, enum.Enum):
    """PRD10 §5.3 ``processing_status`` enum (mirrors ``Job.status``)."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class InboxItemPriority(str, enum.Enum):
    """PRD10 §5.3 ``priority`` enum."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


_INBOX_TYPE_VALUES = ", ".join(f"'{e.value}'" for e in InboxItemType)
_INBOX_STATUS_VALUES = ", ".join(f"'{e.value}'" for e in InboxItemStatus)
_INBOX_PROCESSING_VALUES = ", ".join(
    f"'{e.value}'" for e in InboxItemProcessingStatus
)
_INBOX_PRIORITY_VALUES = ", ".join(f"'{e.value}'" for e in InboxItemPriority)


class Prd10InboxItem(Base):
    """PRD10 §5.3 inbox item.

    A single row tracks one captured input from the user (text note, link, file,
    audio, etc.) before / during / after asynchronous processing. The
    ``Prd10`` prefix is intentional to avoid clashing with the legacy
    ``Item``-backed ``InboxItem`` schema in ``inbox/router.py``.
    """

    __tablename__ = "prd10_inbox_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    type = Column(
        String(20),
        nullable=False,
        default=InboxItemType.TEXT.value,
        index=True,
    )

    title = Column(String(500), nullable=True)
    raw_content = Column(Text, nullable=True)

    source_url = Column(String(2000), nullable=True)
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prd10_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_folder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("kb_folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prd10_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = Column(
        String(20),
        nullable=False,
        default=InboxItemStatus.RECEIVED.value,
        index=True,
    )
    processing_status = Column(
        String(20),
        nullable=False,
        default=InboxItemProcessingStatus.QUEUED.value,
        index=True,
    )
    priority = Column(
        String(20),
        nullable=False,
        default=InboxItemPriority.NORMAL.value,
    )
    auto_process = Column(Boolean, nullable=False, default=True)

    tags = Column(JSON, default=list, nullable=False)
    extra = Column(JSON, default=dict, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index('idx_prd10_inbox_user_created', 'user_id', 'created_at'),
        Index('idx_prd10_inbox_user_status', 'user_id', 'status'),
        Index('idx_prd10_inbox_user_status_created', 'user_id', 'status', 'created_at'),
        Index('idx_prd10_inbox_user_type', 'user_id', 'type'),
        CheckConstraint(
            f"type IN ({_INBOX_TYPE_VALUES})",
            name='ck_prd10_inbox_type',
        ),
        CheckConstraint(
            f"status IN ({_INBOX_STATUS_VALUES})",
            name='ck_prd10_inbox_status',
        ),
        CheckConstraint(
            f"processing_status IN ({_INBOX_PROCESSING_VALUES})",
            name='ck_prd10_inbox_processing_status',
        ),
        CheckConstraint(
            f"priority IN ({_INBOX_PRIORITY_VALUES})",
            name='ck_prd10_inbox_priority',
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Prd10InboxItem(id={self.id}, user={self.user_id}, "
            f"type={self.type}, status={self.status})>"
        )

    def to_prd10_dict(self) -> dict:
        """Serialize to the PRD10 §5.3 InboxItem DTO."""

        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "type": self.type,
            "title": self.title,
            "raw_content": self.raw_content,
            "source_url": self.source_url,
            "source_id": str(self.source_id) if self.source_id else None,
            "status": self.status,
            "processing_status": self.processing_status,
            "priority": self.priority,
            "tags": list(self.tags or []),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_capture_response(self) -> dict:
        """Subset DTO used by ``POST /capture/text|link|file/commit`` responses.

        PRD10 §17.1 expects the response to surface the enriched title /
        tags / folder so the SPA can render the just-saved card immediately
        without doing another ``GET /feed`` round-trip.
        """

        return {
            "id": str(self.id),
            "type": self.type,
            "status": self.status,
            "processing_status": self.processing_status,
            "title": self.title,
            "tags": list(self.tags or []),
            "target_folder_id": (
                str(self.target_folder_id) if self.target_folder_id else None
            ),
            "raw_content": self.raw_content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
