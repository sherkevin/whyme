"""PRD10 generic asynchronous job tracking.

This module owns the canonical ``Job`` table that PRD10 references for any
long-running operation. Domain-specific job tables (e.g. the legacy
``IngestionJob`` for content ingestion) coexist; new PRD10 endpoints always
write through ``Job``.
"""

from agent_os.jobs.models import Job, JobStatus, JobType
from agent_os.jobs.service import (
    create_job,
    mark_job_completed,
    mark_job_failed,
)

__all__ = [
    "Job",
    "JobStatus",
    "JobType",
    "create_job",
    "mark_job_completed",
    "mark_job_failed",
]
