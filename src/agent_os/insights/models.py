"""PRD10 §5.10 Insight ORM (`prd10_insights`).

This is a dedicated PRD10 table separate from the legacy
``garden.models.DailyInsight`` (which is workspace-scoped and tied to PRD7).
PRD10 §5.10 requires a generic insight table that the right-hand panel
populates.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    JSON,
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


class InsightType(str, enum.Enum):
    """PRD10 §5.10 ``insight_type`` enum."""

    THEME_TREND = "theme_trend"
    TASK_RISK = "task_risk"
    KNOWLEDGE_GAP = "knowledge_gap"
    CONNECTION = "connection"
    DAILY_SUMMARY = "daily_summary"
    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_SUMMARY = "monthly_summary"


class InsightStatus(str, enum.Enum):
    """PRD10 §5.10 ``status`` enum."""

    DRAFT = "draft"
    READY = "ready"
    DISMISSED = "dismissed"


_INSIGHT_TYPE_VALUES = ", ".join(f"'{e.value}'" for e in InsightType)
_INSIGHT_STATUS_VALUES = ", ".join(f"'{e.value}'" for e in InsightStatus)


class Prd10Insight(Base):
    """PRD10 §5.10 Insight."""

    __tablename__ = "prd10_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    insight_type = Column(String(40), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    body = Column(Text, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        default=InsightStatus.READY.value,
        index=True,
    )

    related_object_type = Column(String(50), nullable=True)
    related_object_id = Column(String(64), nullable=True)
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
        Index('idx_prd10_insights_user_type', 'user_id', 'insight_type'),
        CheckConstraint(
            f"insight_type IN ({_INSIGHT_TYPE_VALUES})",
            name='ck_prd10_insights_type',
        ),
        CheckConstraint(
            f"status IN ({_INSIGHT_STATUS_VALUES})",
            name='ck_prd10_insights_status',
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Prd10Insight(id={self.id}, user={self.user_id}, "
            f"type={self.insight_type}, status={self.status})>"
        )

    def to_prd10_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "insight_type": self.insight_type,
            "title": self.title,
            "summary": self.summary,
            "body": self.body,
            "status": self.status,
            "related_object_type": self.related_object_type,
            "related_object_id": self.related_object_id,
            "extra": dict(self.extra or {}),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
