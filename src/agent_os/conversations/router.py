"""Conversation history API endpoints."""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.db.base import get_db
from agent_os.conversations import ConversationRepository
from agent_os.conversations.models import Conversation


router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("/{session_id}/history")
async def get_conversation_history(
    session_id: str,
    user_id: int,
    limit: int = 50,
    before_id: int | None = None,
    db: AsyncSession = Depends(get_db),
) -> List[dict]:
    """Get conversation history for a session.

    Args:
        session_id: Session identifier
        user_id: User ID
        limit: Maximum messages to retrieve (default: 50)
        before_id: Get messages before this ID (for pagination)

    Returns:
        List of conversation messages
    """
    repo = ConversationRepository()

    conversations = await repo.get_conversation_history(
        session=db,
        user_id=user_id,
        session_id=session_id,
        limit=limit,
        before_id=before_id,
    )

    return [
        {
            "id": conv.id,
            "role": conv.role,
            "content": conv.content,
            "tool_calls": conv.tool_calls,
            "model": conv.model,
            "tokens": conv.tokens,
            "created_at": conv.created_at.isoformat(),
        }
        for conv in conversations
    ]


@router.get("/{session_id}/tokens")
async def get_session_token_count(
    session_id: str,
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get total token count for a session."""
    repo = ConversationRepository()
    total_tokens = await repo.get_token_count(
        session=db,
        user_id=user_id,
        session_id=session_id,
    )

    return {"session_id": session_id, "total_tokens": total_tokens}


@router.delete("/{conversation_id}")
async def delete_conversation_message(
    conversation_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a conversation message.

    Args:
        conversation_id: Message ID
        user_id: User ID for authorization
    """
    repo = ConversationRepository()

    # Get conversation to verify ownership
    conv = await repo.get_conversation(db, conversation_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    deleted = await repo.delete_conversation(db, conversation_id)

    if deleted:
        await db.commit()
        return {"status": "deleted", "conversation_id": conversation_id}
    else:
        raise HTTPException(status_code=404, detail="Failed to delete conversation")


@router.get("/sessions/recent")
async def get_recent_sessions(
    user_id: int,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
) -> List[str]:
    """Get recent session IDs for a user."""
    repo = ConversationRepository()
    sessions = await repo.get_recent_sessions(db, user_id, limit=limit)
    return sessions
