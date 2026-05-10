"""Conversation history database models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from agent_os.db.base import Base


class Conversation(Base):
    """Conversation history for storing chat messages."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(255), nullable=False, index=True)

    # Message content
    role = Column(String(50), nullable=False)  # 'user', 'assistant', 'system', 'tool'
    content = Column(Text, nullable=False)

    # Tool calls (if role == 'tool')
    tool_calls = Column(JSON, nullable=True)

    # Metadata
    model = Column(String(100))  # Which LLM was used
    tokens = Column(Integer)  # Token count for this message

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    # Note: User model doesn't have conversations backref yet
    # user = relationship("User", back_populates="conversations")

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, user_id={self.user_id}, role={self.role}, session={self.session_id})>"


class ConversationSummary(Base):
    """Conversation summaries for long-running sessions.

    When conversations get too long, they can be summarized
    and older messages archived.
    """

    __tablename__ = "conversation_summaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(255), nullable=False, index=True)

    # Summary
    summary_text = Column(Text, nullable=False)
    message_count = Column(Integer, default=0)  # Number of messages summarized
    total_tokens = Column(Integer, default=0)  # Total tokens in summarized messages

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Index for efficient querying
    __table_args__ = (
        Index('ix_conversation_summaries_user_session', 'user_id', 'session_id'),
    )

    def __repr__(self) -> str:
        return f"<ConversationSummary(id={self.id}, user_id={self.user_id}, messages={self.message_count})>"
