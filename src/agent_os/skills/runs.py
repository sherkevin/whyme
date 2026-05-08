"""PRD10 ``SkillRun`` ORM table (§17).

A SkillRun records a single invocation of a Skill: the input the user
provided, the asynchronous job tracking its execution, and the output once
it finishes. This is the shape ``POST /api/v1/skills/{id}/run`` returns and
``GET /api/v1/jobs/{job_id}`` correlates against.
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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from agent_os.db.base import Base


class SkillRunStatus(str, enum.Enum):
    """Aligned with PRD10 §16 generic job statuses."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


_SKILL_RUN_STATUS_VALUES = ", ".join(f"'{s.value}'" for s in SkillRunStatus)


class SkillRun(Base):
    """PRD10 §17 SkillRun record."""

    __tablename__ = "skill_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    skill_id = Column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prd10_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = Column(String(20), nullable=False, default=SkillRunStatus.QUEUED.value)

    input = Column(JSON, default=dict, nullable=False)
    output = Column(JSON, nullable=True)
    error = Column(JSON, nullable=True)

    save_output = Column(String(20), nullable=True)
    output_object_type = Column(String(50), nullable=True)
    output_object_id = Column(String(64), nullable=True)

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
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_skill_runs_user_status', 'user_id', 'status'),
        Index('idx_skill_runs_skill_created', 'skill_id', 'created_at'),
        CheckConstraint(
            f"status IN ({_SKILL_RUN_STATUS_VALUES})",
            name='ck_skill_runs_status',
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SkillRun(id={self.id}, skill={self.skill_id}, "
            f"status={self.status})>"
        )

    def to_prd10_dict(self) -> dict:
        return {
            "id": str(self.id),
            "skill_id": str(self.skill_id),
            "user_id": str(self.user_id),
            "job_id": str(self.job_id) if self.job_id else None,
            "status": self.status,
            "input": dict(self.input or {}),
            "output": self.output,
            "error": self.error,
            "save_output": self.save_output,
            "output_object_type": self.output_object_type,
            "output_object_id": self.output_object_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
