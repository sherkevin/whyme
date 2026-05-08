"""Helpers for creating ``Notification`` rows.

Domain modules (capture, jobs, AI) call ``create_notification`` instead of
inserting rows directly so the data shape stays consistent and future
fan-out (websocket push, email digest, etc.) has a single hook.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.notifications.broker import publish_notification
from agent_os.notifications.models import Notification, NotificationType


async def create_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: NotificationType | str,
    title: str,
    content: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    workspace_id: uuid.UUID | None = None,
) -> Notification:
    """Insert and flush a notification row."""

    notification = Notification(
        user_id=user_id,
        workspace_id=workspace_id,
        type=type.value if isinstance(type, NotificationType) else type,
        title=title,
        content=content,
        object_type=object_type,
        object_id=object_id,
    )
    db.add(notification)
    await db.flush()
    # Best-effort SSE fanout. Errors are swallowed so tests/transactional
    # paths never fail because of subscriber issues.
    try:
        await publish_notification(notification)
    except Exception:  # pragma: no cover - defensive
        pass
    return notification


def render_capture_notification_title(item_type: str) -> str:
    """Standard title for capture-completed notifications."""

    pretty = {
        "text": "笔记",
        "link": "链接",
        "file": "文件",
        "image": "图片",
        "audio": "音频",
        "video": "视频",
        "manual_task": "任务",
    }.get(item_type, "记录")
    return f"已收到{pretty}"
