"""PRD10 §14 Task API endpoints (UUID identity).

* ``GET    /api/v1/tasks``                — §14.1 list (paginated)
* ``POST   /api/v1/tasks``                — §14.2 create
* ``GET    /api/v1/tasks/{task_id}``      — detail
* ``PATCH  /api/v1/tasks/{task_id}``      — §14.3 partial update
* ``POST   /api/v1/tasks/{task_id}/complete`` — §14.4 mark done + completed_at
* ``DELETE /api/v1/tasks/{task_id}``      — soft delete

The legacy Integer-keyed ``/api/v1/tasks`` router stays mounted afterwards so
its bonus endpoints (``/today``, ``/stats``, ``/batch``) keep working. Path
collisions on ``/api/v1/tasks`` and ``/api/v1/tasks/{uuid}`` are resolved by
FastAPI's first-match rule because this router is included first in
``server/app.py``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import ApiErrorCode, paginated_response, success_response
from agent_os.db.base import get_db
from agent_os.tasks.models import PRD10Task

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks (PRD10)"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


_VALID_STATUS = {"todo", "doing", "done", "canceled"}
_VALID_PRIORITY = {"low", "medium", "high", "urgent"}
_VALID_SOURCE = {"manual", "ai", "inbox", "document", "insight"}


class TaskCreatePrd10(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    priority: Literal["low", "medium", "high", "urgent"] = "medium"
    status: Literal["todo", "doing", "done", "canceled"] = "todo"
    due_at: datetime | None = None
    source_type: Literal["manual", "ai", "inbox", "document", "insight"] = "manual"
    source_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class TaskUpdatePrd10(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    priority: Literal["low", "medium", "high", "urgent"] | None = None
    status: Literal["todo", "doing", "done", "canceled"] | None = None
    due_at: datetime | None = None
    source_type: Literal["manual", "ai", "inbox", "document", "insight"] | None = None
    source_id: str | None = None
    tags: list[str] | None = None
    extra: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validation_error(message: str, field: str | None = None) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": ApiErrorCode.VALIDATION_ERROR.value,
            "message": message,
            "details": {"field": field} if field else None,
        },
    )


def _not_found(message: str = "Task not found") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": ApiErrorCode.NOT_FOUND.value,
            "message": message,
        },
    )


def _parse_due_range(due_range: str | None) -> tuple[datetime | None, datetime | None]:
    """Parse PRD10 §14.1 ``due_range`` shorthand.

    Supported shapes (all ISO timezone-aware, UTC):
      - ``today``     → start of today → end of today
      - ``week``      → start of today → +7d
      - ``overdue``   → epoch → now (status != done)
      - ``upcoming``  → now → +30d
      - ``ISO/ISO``   → explicit start/end pair separated by ``/``
    """

    if not due_range:
        return None, None
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if due_range == "today":
        return today_start, today_start + timedelta(days=1)
    if due_range == "week":
        return today_start, today_start + timedelta(days=7)
    if due_range == "overdue":
        return datetime(1970, 1, 1, tzinfo=UTC), now
    if due_range == "upcoming":
        return now, now + timedelta(days=30)
    if "/" in due_range:
        try:
            start_raw, end_raw = due_range.split("/", 1)
            start = datetime.fromisoformat(start_raw)
            end = datetime.fromisoformat(end_raw)
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)
            return start, end
        except ValueError:
            raise _validation_error(
                "Invalid due_range (expected ISO/ISO or today|week|overdue|upcoming)",
                "due_range",
            )
    raise _validation_error(
        "Invalid due_range (expected today|week|overdue|upcoming|ISO/ISO)",
        "due_range",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_tasks(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    priority: str | None = Query(default=None),
    due_range: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §14.1 — list user's tasks with filters and pagination."""

    if status_filter and status_filter not in _VALID_STATUS:
        raise _validation_error(f"Invalid status '{status_filter}'", "status")
    if priority and priority not in _VALID_PRIORITY:
        raise _validation_error(f"Invalid priority '{priority}'", "priority")
    if source_type and source_type not in _VALID_SOURCE:
        raise _validation_error(f"Invalid source_type '{source_type}'", "source_type")

    start, end = _parse_due_range(due_range)

    base = select(PRD10Task).where(
        PRD10Task.user_id == current_user.id,
        PRD10Task.deleted_at.is_(None),
    )
    if status_filter:
        base = base.where(PRD10Task.status == status_filter)
    if priority:
        base = base.where(PRD10Task.priority == priority)
    if source_type:
        base = base.where(PRD10Task.source_type == source_type)
    if start and end:
        base = base.where(PRD10Task.due_at >= start, PRD10Task.due_at < end)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one() or 0

    rows = (
        await db.execute(
            base.order_by(PRD10Task.due_at.asc().nulls_last(), PRD10Task.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
    ).scalars().all()

    return paginated_response(
        [r.to_prd10_dict() for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
        request=request,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreatePrd10,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §14.2 — create a task."""

    task = PRD10Task(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        status=payload.status,
        due_at=payload.due_at,
        source_type=payload.source_type,
        source_id=payload.source_id,
        tags=list(payload.tags or []),
        extra=dict(payload.extra or {}),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return success_response(task.to_prd10_dict(), request=request)


@router.get("/{task_id}")
async def get_task(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Task detail."""

    tid = task_id
    row = (
        await db.execute(
            select(PRD10Task).where(
                PRD10Task.id == tid,
                PRD10Task.user_id == current_user.id,
                PRD10Task.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise _not_found()
    return success_response(row.to_prd10_dict(), request=request)


@router.patch("/{task_id}")
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdatePrd10,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §14.3 — partial update."""

    tid = task_id
    row = (
        await db.execute(
            select(PRD10Task).where(
                PRD10Task.id == tid,
                PRD10Task.user_id == current_user.id,
                PRD10Task.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise _not_found()

    updates = payload.model_dump(exclude_unset=True)
    if "tags" in updates and updates["tags"] is not None:
        updates["tags"] = list(updates["tags"])
    if "extra" in updates and updates["extra"] is not None:
        updates["extra"] = dict(updates["extra"])

    for field, value in updates.items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return success_response(row.to_prd10_dict(), request=request)


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """PRD10 §14.4 — flip status to ``done`` and stamp ``completed_at``."""

    tid = task_id
    row = (
        await db.execute(
            select(PRD10Task).where(
                PRD10Task.id == tid,
                PRD10Task.user_id == current_user.id,
                PRD10Task.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise _not_found()
    row.status = "done"
    row.completed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(row)
    return success_response(row.to_prd10_dict(), request=request)


@router.delete("/{task_id}")
async def delete_task(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Soft-delete (sets ``deleted_at``)."""

    tid = task_id
    row = (
        await db.execute(
            select(PRD10Task).where(
                PRD10Task.id == tid,
                PRD10Task.user_id == current_user.id,
                PRD10Task.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise _not_found()
    row.deleted_at = datetime.now(UTC)
    await db.commit()
    return success_response(
        {"id": str(row.id), "deleted": True}, request=request
    )


__all__ = ["router"]
