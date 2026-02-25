"""Task management models."""

from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Date, Boolean, Index, UUID
import uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from agent_os.db.base import Base


class Task(Base):
    """Task model for task management."""

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # 改为可空，去掉FK
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
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
        Index('idx_task_org_user', 'organization_id', 'user_id'),
        Index('idx_task_org_status', 'organization_id', 'status'),
        Index('idx_task_org_status_date', 'organization_id', 'status', 'scheduled_date'),
    )
