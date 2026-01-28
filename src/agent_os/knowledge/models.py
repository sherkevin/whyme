"""Knowledge management models - Inbox and Cards."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, ARRAY, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from agent_os.db.base import Base

# Vector column type (optional, only used if pgvector is available)
_embedding_column = Column(Integer, nullable=True)  # Placeholder when pgvector not available

try:
    from pgvector.sqlalchemy import Vector
    PGVECTOR_AVAILABLE = True
    # Use real Vector type
    _embedding_column_impl = Vector
except ImportError:
    # pgvector not installed, use placeholder
    PGVECTOR_AVAILABLE = False
    _embedding_column_impl = None


class InboxItem(Base):
    """Inbox item for capturing raw information."""

    __tablename__ = "inbox_items"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    status = Column(String(20), default="raw", index=True)  # raw, processed, archived
    source = Column(String(50))  # manual, api, import
    extra_data = Column(JSON, default={})  # Additional metadata (renamed from metadata)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="inbox_items")
    cards = relationship("Card", back_populates="source_item")

    __table_args__ = (
        # 复合索引优化多租户查询
        Index('idx_inbox_org_user', 'organization_id', 'user_id'),
        Index('idx_inbox_org_status', 'organization_id', 'status'),
    )


class Card(Base):
    """Knowledge card with vector embedding for RAG."""

    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    para_type = Column(String(50), index=True)  # concept, action, reference
    tags = Column(JSON, default=list)  # Tags stored as JSON (works with SQLite and PostgreSQL)
    source_inbox_item_id = Column(Integer, ForeignKey("inbox_items.id", ondelete="SET NULL"))

    # Conditional embedding column (only used if pgvector is available)
    if PGVECTOR_AVAILABLE:
        embedding = Column(_embedding_column_impl(384))  # Vector embedding for RAG
    else:
        embedding = Column(JSON, nullable=True)  # Store as JSON when pgvector not available

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="cards")
    source_item = relationship("InboxItem", back_populates="cards")

    __table_args__ = (
        # 复合索引优化多租户查询
        Index('idx_card_org_user', 'organization_id', 'user_id'),
        Index('idx_card_org_type', 'organization_id', 'para_type'),
        Index('idx_card_org_created', 'organization_id', 'created_at'),
    )
