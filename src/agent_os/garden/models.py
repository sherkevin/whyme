"""Garden models for PRD7 - Knowledge Graph and Insights.

This module contains:
- KnowledgeCardLink: Relationship edges between knowledge cards
- DailyInsight: Insights generated from knowledge processing
"""

import uuid
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from agent_os.db.base import Base


class RelationType(str, Enum):
    """Knowledge card link relation types - PRD7 spec."""
    RELATED = "related"
    SUPPORT = "support"
    CONTRADICT = "contradict"
    REFERENCE = "reference"


class InsightStatus(str, Enum):
    """Daily insight status - PRD7 spec."""
    DRAFT = "draft"
    CANDIDATE = "candidate"
    STABLE = "stable"
    REJECTED = "rejected"


class KnowledgeCardLink(Base):
    """Knowledge card relationship edges - PRD7 Knowledge Garden.

    This model represents the relationships between knowledge cards (Items),
    supporting the cognitive graph for knowledge organization.

    Attributes:
        id: UUID primary key
        workspace_id: Workspace this edge belongs to
        from_id: Source card/item ID
        to_id: Target card/item ID
        type: Relationship type (related/support/contradict/reference)
        relation_strength: Strength of the relationship [0.0, 1.0]
        is_active: Soft delete flag
        created_at: Creation timestamp
        updated_at: Auto-update timestamp
    """

    __tablename__ = "knowledge_card_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    from_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    to_id = Column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False)

    # Relation type with enum constraint
    type = Column(String(20), nullable=False)

    # PRD7 new fields
    relation_strength = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # Unique constraint: prevent duplicate edges of same type between same nodes
        UniqueConstraint('from_id', 'to_id', 'type', name='uq_knowledge_card_link_from_to_type'),
        # Check constraints
        CheckConstraint(
            "type IN ('related', 'support', 'contradict', 'reference')",
            name='ck_knowledge_card_link_type'
        ),
        CheckConstraint(
            "relation_strength >= 0.0 AND relation_strength <= 1.0",
            name='ck_knowledge_card_link_strength_range'
        ),
        # Performance indexes
        Index('idx_kcl_workspace_strength', 'workspace_id', 'relation_strength'),
        Index('idx_kcl_from_id', 'from_id'),
        Index('idx_kcl_to_id', 'to_id'),
    )

    def __repr__(self):
        return f"<KnowledgeCardLink(from={self.from_id}, to={self.to_id}, type={self.type})>"


class DailyInsight(Base):
    """Daily insight model - PRD7 Knowledge Garden.

    This model stores insights generated from knowledge processing,
    supporting the insight lifecycle from draft to stable.

    Attributes:
        id: UUID primary key
        workspace_id: Workspace this insight belongs to
        user_id: User who owns this insight
        title: Insight title/summary
        content: Full insight content
        status: Current status (draft/candidate/stable/rejected)
        level: Insight level (1/2/3)
        canonical_hash: Hash for deduplication
        stability_score: Stability score [0.0, 1.0]
        evidence_count: Number of supporting evidence items
        source_item_ids: JSON array of source item IDs
        created_at: Creation timestamp
        updated_at: Auto-update timestamp
    """

    __tablename__ = "daily_insights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Core content
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)

    # PRD7 fields
    status = Column(String(20), nullable=False, default="draft")
    level = Column(Integer, nullable=False, default=1)
    canonical_hash = Column(String(64), nullable=True, index=True)  # SHA-256 hash
    stability_score = Column(Float, nullable=False, default=0.0)
    evidence_count = Column(Integer, nullable=False, default=1)

    # Source tracking
    source_item_ids = Column(Text, nullable=True)  # JSON array of item IDs

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # Check constraints for enum validation
        CheckConstraint(
            "status IN ('draft', 'candidate', 'stable', 'rejected')",
            name='ck_daily_insight_status'
        ),
        CheckConstraint(
            "level IN (1, 2, 3)",
            name='ck_daily_insight_level'
        ),
        CheckConstraint(
            "stability_score >= 0.0 AND stability_score <= 1.0",
            name='ck_daily_insight_stability_range'
        ),
        CheckConstraint(
            "evidence_count >= 1",
            name='ck_daily_insight_evidence_min'
        ),
        # Performance indexes
        Index('idx_di_workspace_user', 'workspace_id', 'user_id'),
        Index('idx_di_status', 'status'),
        Index('idx_di_created_at', 'created_at'),
        Index('idx_di_canonical_hash', 'canonical_hash'),
    )

    def __repr__(self):
        return f"<DailyInsight(id={self.id}, status={self.status}, level={self.level})>"