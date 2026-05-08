"""Knowledge management models - Cards for Stage 2."""

import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from agent_os.db.base import Base


class InboxItem(Base):
    """Raw inbox capture entry.

    PRD10 uses `InboxItem` as the entry point for any user-submitted content
    (text, link, file, image, audio) before it is normalized/parsed. The
    canonical PRD4 storage today is `agent_os.items.models.Item`, but several
    legacy tests still expect this dedicated table. We keep both alive: legacy
    tests get this minimal model so they can collect, while PRD10 endpoints
    will write through this table directly with the schema below.
    """

    __tablename__ = "inbox_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    content = Column(Text, nullable=False)
    title = Column(String(500), nullable=True)
    summary = Column(Text, nullable=True)

    item_type = Column(String(50), default="note", nullable=False)
    source_type = Column(String(50), default="manual", nullable=False, index=True)
    source_meta = Column(JSON, default=dict, nullable=False)

    status = Column(String(50), default="raw", nullable=False, index=True)

    extra_data = Column(JSON, default=dict, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index('idx_inbox_items_user_status', 'user_id', 'status'),
        Index('idx_inbox_items_user_created', 'user_id', 'created_at'),
        Index('idx_inbox_items_source_type', 'source_type'),
    )

    def __repr__(self):
        return f"<InboxItem(id={self.id}, user_id={self.user_id}, status={self.status})>"


class Card(Base):
    """Knowledge card.

    PRD10 §5.5 Card is the shape consumed by the Feed. The original Stage 2
    schema kept only ``title/content/para_type/tags``; the additional columns
    below are required by PRD10 (`summary`, `cover_url`, `content_type`,
    folder/source/inbox links, favorite/archived flags, entities, visibility).
    All new columns are nullable / have safe defaults so existing rows remain
    valid.
    """

    __tablename__ = "cards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)

    para_type = Column(String(50), index=True)  # legacy (concept/action/reference)
    content_type = Column(String(50), nullable=False, default="note", index=True)

    cover_url = Column(String(2000), nullable=True)
    tags = Column(JSON, default=list)
    entities = Column(JSON, default=list)

    source_inbox_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("items.id", ondelete="SET NULL"),
        nullable=True,
    )
    inbox_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prd10_inbox_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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

    is_favorite = Column(Boolean, nullable=False, default=False, index=True)
    is_archived = Column(Boolean, nullable=False, default=False, index=True)
    visibility = Column(String(20), nullable=False, default="private")

    embedding = Column(JSON, nullable=True)

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

    source_item = relationship("Item", foreign_keys=[source_inbox_item_id])

    __table_args__ = (
        Index('idx_card_user_created', 'user_id', 'created_at'),
        Index('idx_card_user_content_type', 'user_id', 'content_type'),
        Index('idx_card_user_folder', 'user_id', 'folder_id'),
        Index('idx_card_user_favorite', 'user_id', 'is_favorite'),
        Index('idx_card_user_tags', 'user_id', 'tags').ddl_if(dialect='sqlite'),
    )

    def to_prd10_dict(self) -> dict:
        """Serialize to PRD10 §5.5 Card DTO."""

        source_payload = None
        if self.source_id:
            source_payload = {"id": str(self.source_id)}

        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "title": self.title,
            "summary": self.summary,
            "cover_url": self.cover_url,
            "content_type": self.content_type,
            "source": source_payload,
            "source_id": str(self.source_id) if self.source_id else None,
            "inbox_item_id": str(self.inbox_item_id) if self.inbox_item_id else None,
            "folder_id": str(self.folder_id) if self.folder_id else None,
            "tags": list(self.tags or []),
            "entities": list(self.entities or []),
            "is_favorite": self.is_favorite,
            "is_archived": self.is_archived,
            "visibility": self.visibility,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_feed_dict(self) -> dict:
        """Subset DTO used by ``GET /feed`` items per PRD10 §9.1."""

        return {
            "id": str(self.id),
            "inbox_item_id": (
                str(self.inbox_item_id) if self.inbox_item_id else None
            ),
            "title": self.title,
            "summary": self.summary,
            "cover_url": self.cover_url,
            "content_type": self.content_type,
            "tags": list(self.tags or []),
            "folder_id": str(self.folder_id) if self.folder_id else None,
            "source": (
                {"id": str(self.source_id), "type": "card"}
                if self.source_id
                else None
            ),
            "is_favorite": self.is_favorite,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
