"""PRD10 ``/api/v1/jobs/*`` router.

Implements:

- ``GET /api/v1/jobs/{job_id}``  (PRD10 §16.1)
- ``POST /api/v1/jobs/{job_id}/cancel`` (PRD10 §16.2)

Domain modules write through ``agent_os.jobs.service.create_job`` to keep
storage shape uniform.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import ApiErrorCode, success_response
from agent_os.db.base import get_db
from agent_os.jobs.models import Job, JobStatus

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.get("/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return job state in PRD10 §16.1 envelope."""

    job = await _load_owned_job(db, job_id, current_user.id)
    return success_response(job.to_prd10_dict(), request=request)


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a job that is still queued or running.

    Idempotent: cancelling an already-canceled job returns the job state.
    Cancelling a completed/failed job returns ``VALIDATION_ERROR``.
    """

    job = await _load_owned_job(db, job_id, current_user.id)

    if job.status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ApiErrorCode.VALIDATION_ERROR.value,
                "message": f"Job already {job.status}",
            },
        )

    if job.status != JobStatus.CANCELED.value:
        job.status = JobStatus.CANCELED.value
        await db.commit()
        await db.refresh(job)

    return success_response(job.to_prd10_dict(), request=request)


async def _load_owned_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Job:
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": ApiErrorCode.NOT_FOUND.value,
                "message": "Job not found",
            },
        )
    return job
