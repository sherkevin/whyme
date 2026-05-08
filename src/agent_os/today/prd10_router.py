"""PRD10 §7 ``GET /api/v1/today`` aggregator."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.common import success_response
from agent_os.db.base import get_db
from agent_os.inbox.prd10_models import Prd10InboxItem
from agent_os.kb.models import Document, Folder
from agent_os.tasks.models import PRD10Task

router = APIRouter(prefix="/api/v1", tags=["Today"])


_QUICK_ACTIONS = [
    {"key": "text", "label": "记录想法", "icon": "edit"},
    {"key": "link", "label": "添加链接", "icon": "link"},
    {"key": "audio", "label": "语音输入", "icon": "mic"},
    {"key": "file", "label": "上传文件", "icon": "upload"},
]


@router.get("/today")
async def get_today(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    timezone_name: str | None = Query(default=None, alias="timezone"),
):
    today_start = _today_start(timezone_name)
    week_start = today_start - timedelta(days=7)
    prev_week_start = today_start - timedelta(days=14)

    today_capture_count = await _count(
        db,
        select(func.count(Prd10InboxItem.id)).where(
            Prd10InboxItem.user_id == current_user.id,
            Prd10InboxItem.created_at >= today_start,
        ),
    )

    knowledge_items_count = await _count(
        db,
        select(func.count(Document.id)).where(
            Document.user_id == current_user.id,
            Document.deleted_at.is_(None),
        ),
    )

    week_count = await _count(
        db,
        select(func.count(Prd10InboxItem.id)).where(
            Prd10InboxItem.user_id == current_user.id,
            Prd10InboxItem.created_at >= week_start,
        ),
    )
    prev_week_count = await _count(
        db,
        select(func.count(Prd10InboxItem.id)).where(
            Prd10InboxItem.user_id == current_user.id,
            Prd10InboxItem.created_at >= prev_week_start,
            Prd10InboxItem.created_at < week_start,
        ),
    )

    weekly_growth_rate = (
        ((week_count - prev_week_count) / prev_week_count)
        if prev_week_count
        else (1.0 if week_count else 0.0)
    )

    task_rows = (
        await db.execute(
            select(PRD10Task)
            .where(
                PRD10Task.user_id == current_user.id,
                PRD10Task.deleted_at.is_(None),
                PRD10Task.status != "canceled",
            )
            .order_by(PRD10Task.due_at.asc().nulls_last(), PRD10Task.created_at.desc())
            .limit(5)
        )
    ).scalars().all()

    pending_task_count = await _count(
        db,
        select(func.count(PRD10Task.id)).where(
            PRD10Task.user_id == current_user.id,
            PRD10Task.deleted_at.is_(None),
            PRD10Task.status.in_(("todo", "doing")),
        ),
    )

    tasks_payload = [
        row.to_prd10_dict()
        for row in task_rows
    ]

    payload: dict[str, Any] = {
        "user": {
            "id": str(current_user.id),
            "name": current_user.username,
            "username": current_user.username,
            "email": current_user.email,
            "avatar_url": current_user.avatar_url,
            "is_active": bool(current_user.is_active),
        },
        "stats": {
            "today_capture_count": today_capture_count,
            "pending_task_count": pending_task_count,
            "knowledge_items_count": knowledge_items_count,
            "weekly_growth_rate": round(weekly_growth_rate, 4),
        },
        "quick_actions": _QUICK_ACTIONS,
        "tasks": tasks_payload,
        "insight_preview": {
            "title": "暂无洞察",
            "summary": "继续记录会让我们生成你的第一条洞察。",
        },
    }

    # Tiny ergonomics: include the 3 most recently updated favorite folders so
    # the home view can surface knowledge entry points without waiting for KB.
    favorite_folders = (
        await db.execute(
            select(Folder)
            .where(
                Folder.user_id == current_user.id,
                Folder.deleted_at.is_(None),
                Folder.is_favorite.is_(True),
            )
            .order_by(Folder.updated_at.desc())
            .limit(3)
        )
    ).scalars().all()
    payload["favorite_folders"] = [folder.to_prd10_dict() for folder in favorite_folders]

    return success_response(payload, request=request)


async def _count(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar_one() or 0)


def _today_start(timezone_name: str | None) -> datetime:
    """Return today's local-midnight as UTC for deterministic comparisons."""

    # Without zoneinfo we still get a stable reference because all writes use
    # ``server_default=func.now()`` (UTC). For V1 we pin to UTC midnight; the
    # ``timezone`` query parameter is accepted but ignored and recorded for
    # the next slice.
    _ = timezone_name
    now = datetime.now(UTC)
    return datetime.combine(now.date(), time.min, tzinfo=UTC)


__all__ = ["router"]
