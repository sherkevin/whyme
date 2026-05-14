"""PRD10 Knowledge Base ORM models (§5.6 Folder, §5.7 Document/Chunk)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
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


class DocumentType(str, enum.Enum):
    """PRD10 §5.7 document_type enum."""

    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    MARKDOWN = "markdown"
    TEXT = "text"
    LINK = "link"
    AUDIO = "audio"
    IMAGE = "image"
    NOTE = "note"


class DocumentStatus(str, enum.Enum):
    """PRD10 §5.7 status enum."""

    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"


class Folder(Base):
    """PRD10 §5.6 KB folder.

    A folder is a tree node owned by a user/workspace. It is **not** the same
    as ``items.models.Area`` — Areas belong to PRD4's life-area taxonomy. KB
    folders hold documents/cards and can nest.
    """

    __tablename__ = "kb_folders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prd10_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("kb_folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)
    icon = Column(String(50), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_favorite = Column(Boolean, nullable=False, default=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    parent = relationship("Folder", remote_side=[id], backref="children")

    __table_args__ = (
        Index('idx_kb_folders_user_parent', 'user_id', 'parent_id'),
        Index('idx_kb_folders_user_name', 'user_id', 'name'),
    )

    def __repr__(self) -> str:
        return f"<Folder(id={self.id}, name={self.name!r}, user={self.user_id})>"

    def to_prd10_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "name": self.name,
            "description": sanitize_public_text(self.description),
            "color": self.color,
            "icon": self.icon,
            "sort_order": self.sort_order,
            "is_favorite": self.is_favorite,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Document(Base):
    """PRD10 §5.7 KB document.

    A document is the primary unit users browse in the knowledge base. It can
    derive from a Source (file/link) or be authored directly. Chunks live in
    a child table and feed embeddings + search.
    """

    __tablename__ = "kb_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    folder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("kb_folders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prd10_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title = Column(String(500), nullable=False)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)

    document_type = Column(String(20), nullable=False, default=DocumentType.NOTE.value, index=True)
    status = Column(String(20), nullable=False, default=DocumentStatus.READY.value, index=True)

    tags = Column(JSON, default=list, nullable=False)
    extra = Column(JSON, default=dict, nullable=False)

    is_favorite = Column(Boolean, nullable=False, default=False, index=True)
    word_count = Column(Integer, nullable=True)

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

    folder = relationship("Folder", foreign_keys=[folder_id])

    __table_args__ = (
        Index('idx_kb_documents_user_folder_updated', 'user_id', 'folder_id', 'updated_at'),
        Index('idx_kb_documents_user_updated', 'user_id', 'updated_at'),
        Index('idx_kb_documents_user_status', 'user_id', 'status'),
        Index('idx_kb_documents_user_type', 'user_id', 'document_type'),
    )

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, user={self.user_id}, "
            f"title={self.title!r}, status={self.status})>"
        )

    def to_prd10_dict(self, *, include_content: bool = False) -> dict:
        payload: dict = {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "folder_id": str(self.folder_id) if self.folder_id else None,
            "source_id": str(self.source_id) if self.source_id else None,
            "title": sanitize_public_text(self.title),
            "summary": sanitize_public_text(self.summary),
            "document_type": self.document_type,
            "status": self.status,
            "tags": list(self.tags or []),
            "is_favorite": self.is_favorite,
            "word_count": self.word_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_content:
            payload["content"] = sanitize_public_text(self.content)
        return payload


class Chunk(Base):
    """PRD10 §5.7 KB chunk — embedding-ready text fragment of a document."""

    __tablename__ = "kb_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prd10_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=True)

    extra = Column(JSON, default=dict, nullable=False)

    embedding_id = Column(String(100), nullable=True)
    embedding = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    document = relationship("Document", foreign_keys=[document_id])

    __table_args__ = (
        Index('idx_kb_chunks_doc_index', 'document_id', 'chunk_index'),
        Index('idx_kb_chunks_user_doc', 'user_id', 'document_id'),
        Index('idx_kb_chunks_user_source', 'user_id', 'source_id'),
    )

    def __repr__(self) -> str:
        return (
            f"<Chunk(doc={self.document_id}, index={self.chunk_index}, "
            f"tokens={self.token_count})>"
        )

    def to_prd10_dict(self) -> dict:
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "source_id": str(self.source_id) if self.source_id else None,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "token_count": self.token_count,
            "metadata": dict(self.extra or {}),
        }
