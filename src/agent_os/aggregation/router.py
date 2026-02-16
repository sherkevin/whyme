"""聚合接口 - 提供今日统一视图."""

from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.db.base import get_db
from agent_os.conversations import ConversationRepository
from agent_os.auth.models import User
# TODO: Implement InboxItem model
# from agent_os.knowledge.models import Card
from agent_os.items.models import Item as InboxItem
from agent_os.knowledge.models import Card
from agent_os.tasks.models import Task
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User


router = APIRouter(prefix="/api/v1", tags=["aggregation"])


@router.get("/today")
async def get_today_summary(
    user_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:

    """Get today's unified summary across all modules.

    Returns:
        Dictionary containing:
        - inbox_stats: 收件箱统计
        - tasks: 今日任务列表
        - knowledge_context: 相关知识卡片
        - recent_conversations: 最近对话
    """
    user_id = None  # TODO: Get from authenticated user

    if user_id is None:
        return {"error": "User ID required"}

    # Initialize repositories
    conv_repo = ConversationRepository()

    # Fetch data in parallel
    import asyncio

    async def fetch_inbox_stats() -> dict:
        """Get inbox statistics."""
        query = f"""
        SELECT
            COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
            COUNT(*) FILTER (WHERE status = 'processed') as processed_count,
            COUNT(*) as total_count
        FROM inbox_items
        WHERE user_id = {user_id}
        """
        result = await db.execute(query)
        row = result.first()
        if row:
            return {
                "pending": row[0],
                "processed": row[1],
                "total": row[2]
            }
        return {"pending": 0, "processed": 0, "total": 0}

    async def fetch_today_tasks() -> list[dict]:
        """Get today's tasks."""
        from sqlalchemy import select, func, date

        today = date.today()
        query = select(Task).where(
            Task.user_id == user_id,
            func.date(Task.due_date) == today
        ).order_by(Task.due_date.asc())

        result = await db.execute(query)
        tasks = result.scalars().all()

        return [
            {
                "id": task.id,
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "estimated_time": task.estimated_time_minutes,
            }
            for task in tasks
        ]

    async def fetch_knowledge_context() -> dict:
        """Get relevant knowledge cards from today."""
        from sqlalchemy import select, func, date

        today = date.today()
        query = select(Card).where(
            Card.user_id == user_id,
            func.date(Card.created_at) == today
        ).order_by(Card.created_at.desc()).limit(5)

        result = await db.execute(query)
        cards = result.scalars().all()

        return {
            "recent_cards": [
                {
                    "id": card.id,
                    "title": card.title,
                    "tags": card.tags,
                    "source": card.source,
                    "created_at": card.created_at.isoformat(),
                }
                for card in cards
            ],
            "total_today": len(cards)
        }

    async def fetch_recent_conversations() -> list[dict]:
        """Get recent conversation sessions."""
        session_ids = await conv_repo.get_recent_sessions(db, user_id, limit=5)

        conversations = []
        for session_id in session_ids:
            convs = await conv_repo.get_conversation_history(
                db, user_id, session_id, limit=5
            )
            for conv in convs:
                conversations.append({
                    "id": conv.id,
                    "session_id": conv.session_id,
                    "role": conv.role,
                    "content": conv.content[:200] + "..." if len(conv.content) > 200 else conv.content,
                    "created_at": conv.created_at.isoformat(),
                })

        return conversations

    # Execute all queries in parallel
    results = await asyncio.gather(
        fetch_inbox_stats(),
        fetch_today_tasks(),
        fetch_knowledge_context(),
        fetch_recent_conversations(),
    )

    inbox_stats, today_tasks, knowledge_context, recent_conversations = results

    return {
        "inbox": inbox_stats,
        "tasks": today_tasks,
        "knowledge": knowledge_context,
        "conversations": recent_conversations,
        "summary": {
            "total_inbox": inbox_stats.get("total", 0),
            "pending_inbox": inbox_stats.get("pending", 0),
            "total_tasks": len(today_tasks),
            "pending_tasks": len([t for t in today_tasks if t["status"] != "done"]),
            "recent_knowledge": knowledge_context.get("total_today", 0),
            "active_sessions": len(recent_conversations),
        }
    }


@router.get("/today/summary")
async def get_today_summary_simple(
    user_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ) -> dict[str, Any]:
    if user_id is None and current_user:
        user_id = str(current_user.id)
    if user_id is None:
        return {"error": "User ID required"}
    full_summary = await get_today_summary(user_id=user_id, current_user=current_user, db=db)
    return full_summary.get("summary", {})

