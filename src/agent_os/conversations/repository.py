"""Conversation database operations."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Conversation, ConversationSummary


class ConversationRepository:
    """Repository for conversation history operations."""

    async def add_message(
        self,
        session: AsyncSession,
        user_id: int,
        session_id: str,
        role: str,
        content: str,
        tool_calls: dict | None = None,
        model: str | None = None,
        tokens: int | None = None,
    ) -> Conversation:
        """Add a message to conversation history.

        Args:
            session: Database session
            user_id: User ID
            session_id: Session identifier
            role: Message role ('user', 'assistant', 'system', 'tool')
            content: Message content
            tool_calls: Tool call information (if role == 'tool')
            model: LLM model name
            tokens: Token count

        Returns:
            Created Conversation object
        """
        conversation = Conversation(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            model=model,
            tokens=tokens,
        )

        session.add(conversation)
        await session.flush()
        return conversation

    async def get_conversation_history(
        self,
        session: AsyncSession,
        user_id: int,
        session_id: str,
        limit: int | None = None,
        before_id: int | None = None,
    ) -> list[Conversation]:
        """Retrieve conversation history.

        Args:
            session: Database session
            user_id: User ID
            session_id: Session identifier
            limit: Maximum number of messages to retrieve
            before_id: Only get messages before this ID (for pagination)

        Returns:
            List of conversations, ordered by created_at DESC (newest first)
        """
        query = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.session_id == session_id,
        )

        if before_id is not None:
            query = query.where(Conversation.id < before_id)

        query = query.order_by(Conversation.created_at.desc())

        if limit is not None:
            query = query.limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_conversation(
        self,
        session: AsyncSession,
        conversation_id: int,
    ) -> Conversation | None:
        """Get a specific conversation by ID.

        Args:
            session: Database session
            conversation_id: Conversation ID

        Returns:
            Conversation object or None
        """
        query = select(Conversation).where(Conversation.id == conversation_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def delete_conversation(
        self,
        session: AsyncSession,
        conversation_id: int,
    ) -> bool:
        """Delete a conversation message.

        Args:
            session: Database session
            conversation_id: Conversation ID

        Returns:
            True if deleted, False if not found
        """
        query = select(Conversation).where(Conversation.id == conversation_id)
        result = await session.execute(query)
        conversation = result.scalar_one_or_none()

        if conversation:
            await session.delete(conversation)
            return True
        return False

    async def get_token_count(
        self,
        session: AsyncSession,
        user_id: int,
        session_id: str,
    ) -> int:
        """Get total token count for a session.

        Args:
            session: Database session
            user_id: User ID
            session_id: Session identifier

        Returns:
            Total token count
        """
        query = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.session_id == session_id,
        )

        result = await session.execute(query)
        conversations = list(result.scalars().all())

        return sum(c.tokens or 0 for c in conversations)

    async def create_summary(
        self,
        session: AsyncSession,
        user_id: int,
        session_id: str,
        summary_text: str,
        message_ids: list[int],
    ) -> ConversationSummary:
        """Create a conversation summary and archive old messages.

        Args:
            session: Database session
            user_id: User ID
            session_id: Session identifier
            summary_text: Summary text
            message_ids: IDs of messages to summarize

        Returns:
            Created ConversationSummary object
        """
        # Get total tokens for messages being summarized
        query = select(Conversation).where(Conversation.id.in_(message_ids))
        result = await session.execute(query)
        conversations = list(result.scalars().all())
        total_tokens = sum(c.tokens or 0 for c in conversations)

        summary = ConversationSummary(
            user_id=user_id,
            session_id=session_id,
            summary_text=summary_text,
            message_count=len(message_ids),
            total_tokens=total_tokens,
        )

        session.add(summary)
        await session.flush()
        return summary

    async def get_recent_sessions(
        self,
        session: AsyncSession,
        user_id: int,
        limit: int = 10,
    ) -> list[str]:
        """Get recent session IDs for a user.

        Args:
            session: Database session
            user_id: User ID
            limit: Maximum number of sessions to return

        Returns:
            List of session IDs, ordered by most recent message
        """
        # Subquery to get latest message time per session
        from sqlalchemy import func

        subquery = (
            select(
                Conversation.session_id,
                func.max(Conversation.created_at).label('last_message_time'),
            )
            .where(Conversation.user_id == user_id)
            .group_by(Conversation.session_id)
            .order_by(func.max(Conversation.created_at).desc())
            .limit(limit)
        )

        result = await session.execute(subquery)
        return [row[0] for row in result.all()]
