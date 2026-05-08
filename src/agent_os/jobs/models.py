"""PRD10 generic ``Job`` table.

PRD10 §5.15 freezes the job statuses and types. Every PRD10 endpoint that
returns a job (capture, parse_file, summarize, ai_chat, skill_run, ...) writes
through this single table so the API ``GET /api/v1/jobs/{id}`` can serve them
uniformly.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from agent_os.db.base import Base


class JobStatus(str, enum.Enum):
    """PRD10 §16.1 / §20.4 / §24 canonical job statuses."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class JobType(str, enum.Enum):
    """PRD10 §5.15 ``job_type`` enum."""

    PARSE_FILE = "parse_file"
    SUMMARIZE = "summarize"
    EMBED = "embed"
    INDEX = "index"
    GENERATE_INSIGHT = "generate_insight"
    GENERATE_REPORT = "generate_report"
    AI_CHAT = "ai_chat"
    SKILL_RUN = "skill_run"


_JOB_STATUS_VALUES = ", ".join(f"'{s.value}'" for s in JobStatus)
_JOB_TYPE_VALUES = ", ".join(f"'{t.value}'" for t in JobType)


class Job(Base):
    """Generic PRD10 asynchronous job.

    The canonical place to read job state is ``GET /api/v1/jobs/{id}``. This
    table holds enough payload (input, output, error) for the API to render
    PRD10's required job DTO without joining any domain table.
    """

    __tablename__ = "prd10_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    job_type = Column(String(50), nullable=False, index=True)
    status = Column(
        String(20),
        nullable=False,
        default=JobStatus.QUEUED.value,
        index=True,
    )
    progress = Column(Integer, nullable=False, default=0)

    input = Column(JSON, default=dict, nullable=False)
    output = Column(JSON, default=None, nullable=True)
    error = Column(JSON, default=None, nullable=True)

    correlation_id = Column(String(100), nullable=True, index=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
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
        Index('idx_prd10_jobs_user_status_created', 'user_id', 'status', 'created_at'),
        Index('idx_prd10_jobs_user_type', 'user_id', 'job_type'),
        CheckConstraint(
            f"status IN ({_JOB_STATUS_VALUES})",
            name='ck_prd10_jobs_status',
        ),
        CheckConstraint(
            f"job_type IN ({_JOB_TYPE_VALUES})",
            name='ck_prd10_jobs_job_type',
        ),
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name='ck_prd10_jobs_progress_range',
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Job(id={self.id}, type={self.job_type}, "
            f"status={self.status}, progress={self.progress})>"
        )

    def to_prd10_dict(self) -> dict:
        """Serialize to PRD10 §16.1 job DTO."""

        return {
            "id": str(self.id),
            "job_type": self.job_type,
            "status": self.status,
            "progress": self.progress,
            "input": self.input or {},
            "output": self.output,
            "error": self.error,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
