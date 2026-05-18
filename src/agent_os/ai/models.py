"""PRD10 Mydow AI ORM models (§5.11 AIConversation, §5.12 AIMessage).

PRD10 separates the **conversation header** from individual **messages**.
The legacy ``agent_os.conversations.models.Conversation`` is a single-message
table inherited from the Aider workspace; we do **not** reuse it here. New
PRD10 endpoints write through ``ai_conversations`` + ``ai_messages``.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from agent_os.common.public_text import sanitize_public_text
from agent_os.db.base import Base


class AIConversationMode(str, enum.Enum):
    """PRD10 §5.11 conversation mode (free-form by V1 spec)."""

    GENERAL = "general"
    KNOWLEDGE = "knowledge"
    PLANNING = "planning"
    REPORT = "report"


class AIMessageRole(str, enum.Enum):
    """PRD10 §5.12 message role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class AIMessageStatus(str, enum.Enum):
    """PRD10 §5.12 message status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


_AI_MSG_ROLE_VALUES = ", ".join(f"'{r.value}'" for r in AIMessageRole)
_AI_MSG_STATUS_VALUES = ", ".join(f"'{s.value}'" for s in AIMessageStatus)


class AIConversation(Base):
    """PRD10 §5.11 AI conversation header.

    Stores summary metadata (title, mode, last preview, count). Message
    content lives in ``AIMessage``.
    """

    __tablename__ = "ai_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    title = Column(String(255), nullable=False, default="新的对话")
    mode = Column(String(50), nullable=False, default=AIConversationMode.GENERAL.value)

    last_message_preview = Column(Text, nullable=True)
    message_count = Column(Integer, nullable=False, default=0)

    context_scope = Column(JSON, default=dict, nullable=False)
    extra = Column(JSON, default=dict, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    messages = relationship(
        "AIMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.created_at",
    )

    __table_args__ = (
        Index('idx_ai_conv_user_updated', 'user_id', 'updated_at'),
        Index('idx_ai_conv_user_created', 'user_id', 'created_at'),
    )

    def __repr__(self) -> str:
        return (
            f"<AIConversation(id={self.id}, user={self.user_id}, "
            f"title={self.title!r}, count={self.message_count})>"
        )

    def to_prd10_dict(self) -> dict:
        extra = self.extra if isinstance(self.extra, dict) else {}
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "title": sanitize_public_text(self.title),
            "mode": self.mode,
            "last_message_preview": sanitize_public_text(self.last_message_preview),
            "message_count": self.message_count,
            "context_scope": self.context_scope or {},
            "pinned": bool(extra.get("pinned", False)),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AIMessage(Base):
    """PRD10 §5.12 AI message (with citations + tool_calls)."""

    __tablename__ = "ai_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False, default="")
    status = Column(String(20), nullable=False, default=AIMessageStatus.COMPLETED.value)

    citations = Column(JSON, default=list, nullable=False)
    tool_calls = Column(JSON, default=list, nullable=False)
    attachments = Column(JSON, default=list, nullable=False)

    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prd10_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error = Column(JSON, nullable=True)

    parent_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    model = Column(String(100), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    conversation = relationship("AIConversation", back_populates="messages")

    __table_args__ = (
        Index('idx_ai_msg_conv_created', 'conversation_id', 'created_at'),
        Index('idx_ai_msg_user_created', 'user_id', 'created_at'),
        CheckConstraint(
            f"role IN ({_AI_MSG_ROLE_VALUES})",
            name='ck_ai_messages_role',
        ),
        CheckConstraint(
            f"status IN ({_AI_MSG_STATUS_VALUES})",
            name='ck_ai_messages_status',
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AIMessage(id={self.id}, conv={self.conversation_id}, "
            f"role={self.role}, status={self.status})>"
        )

    def to_prd10_dict(self) -> dict:
        return {
            "id": str(self.id),
            "conversation_id": str(self.conversation_id),
            "user_id": str(self.user_id),
            "role": self.role,
            "content": sanitize_public_text(self.content) or "",
            "status": self.status,
            "citations": list(self.citations or []),
            "tool_calls": list(self.tool_calls or []),
            "attachments": list(self.attachments or []),
            "error": self.error,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
