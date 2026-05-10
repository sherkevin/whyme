"""Task management models.

Note: ``Task`` here is the legacy PRD2 task table (integer user_id). PRD10 §5.9
uses UUID identities, so we add ``PRD10Task`` alongside it. New PRD10
endpoints write through ``PRD10Task``; the legacy table stays for old tests.
"""

import uuid

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from agent_os.db.base import Base


class PRD10Task(Base):
    """PRD10 §5.9 task.

    UUID user identity, free-form `source_type` (manual/ai/inbox/document/insight),
    and the same `status` enum the UI uses (todo/doing/done/canceled).
    """

    __tablename__ = "prd10_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    status = Column(String(20), nullable=False, default="todo", index=True)
    priority = Column(String(20), nullable=False, default="medium")

    due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    source_type = Column(String(20), nullable=False, default="manual", index=True)
    source_id = Column(String(64), nullable=True)

    tags = Column(JSON, default=list, nullable=False)
    extra = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    __table_args__ = (
        Index('idx_prd10_tasks_user_status_due', 'user_id', 'status', 'due_at'),
        Index('idx_prd10_tasks_user_priority', 'user_id', 'priority'),
        CheckConstraint(
            "status IN ('todo','doing','done','canceled')",
            name='ck_prd10_tasks_status',
        ),
        CheckConstraint(
            "priority IN ('low','medium','high','urgent')",
            name='ck_prd10_tasks_priority',
        ),
        CheckConstraint(
            "source_type IN ('manual','ai','inbox','document','insight')",
            name='ck_prd10_tasks_source_type',
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PRD10Task(id={self.id}, user={self.user_id}, "
            f"title={self.title!r}, status={self.status})>"
        )

    def to_prd10_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "due_at": self.due_at.isoformat() if self.due_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "tags": list(self.tags or []),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Task(Base):
    """Task model for task management."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    # TODO: Add organizations table and uncomment this
    # organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(200), nullable=False)
    description = Column(Text)
    type = Column(String(50), default="task")  # task, habit, goal
    source = Column(String(50), default="manual")  # manual, ai_generated, recurring
    status = Column(String(20), default="pending", index=True)  # pending, in_progress, completed
    priority = Column(Integer, default=5)  # 1-10 priority
    scheduled_date = Column(Date, index=True)  # Planned date
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    # Note: User model doesn't have tasks backref yet
    # user = relationship("User", back_populates="tasks")

    __table_args__ = (
        # 复合索引优化多租户查询
        # TODO: Re-enable when organizations table exists
        # Index('idx_task_org_user', 'organization_id', 'user_id'),
        # Index('idx_task_org_status', 'organization_id', 'status'),
        # Index('idx_task_org_status_date', 'organization_id', 'status', 'scheduled_date'),
    )
