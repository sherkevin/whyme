"""Knowledge management models - Cards for Stage 2."""

from datetime import datetime
import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from agent_os.db.base import Base


class Card(Base):
    """Knowledge card generated from processed Items.

    This model is designed to work with the PRD4 Item/Workspace model
    which uses UUID primary keys.
    """

    __tablename__ = "cards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    para_type = Column(String(50), index=True)  # concept, action, reference
    tags = Column(JSON, default=list)  # Tags stored as JSON
    source_inbox_item_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="SET NULL"), nullable=True)

    # Embedding for RAG (stored as JSON for SQLite compatibility)
    embedding = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    source_item = relationship("Item", foreign_keys=[source_inbox_item_id])

    __table_args__ = (
        Index('idx_card_workspace_user', 'workspace_id', 'user_id'),
        Index('idx_card_workspace_type', 'workspace_id', 'para_type'),
        Index('idx_card_workspace_created', 'workspace_id', 'created_at'),
    )
