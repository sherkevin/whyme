"""Data models for Stage 4 - Search, Ingestion, and Insight.

PRD10 §5.14 SearchDocument shape is layered on top of the legacy
``SearchIndex`` table. Newly added columns (``user_id``, ``workspace_id``,
``summary``, ``embedding_id``) are nullable so the existing ingestion path
(``SearchService.index_item``) keeps working without modification, while
PRD10 callers (Agent 3 search router) populate them explicitly.
"""

import uuid

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from agent_os.db.base import Base

# PRD10 §5.14 object_type enumeration. Kept as a Python tuple so the
# CheckConstraint string and to_prd10_dict serializer share a single source
# of truth. The constraint name ``check_search_item_type`` is preserved for
# backwards compatibility with ``test_search_index_item_type_constraint``.
_PRD10_OBJECT_TYPES: tuple[str, ...] = (
    "card",
    "document",
    "folder",
    "task",
    "conversation",
    "message",
    "skill",
    "insight",
)

# Legacy object types written by the existing ingestion pipeline. These must
# remain accepted so Agent 2's IngestionService keeps writing through this
# table without changes.
_LEGACY_SEARCH_ITEM_TYPES: tuple[str, ...] = (
    "note",
    "decision_point",
    "workspace",
    "project",
    "resource",
    "test",
)

_ALLOWED_SEARCH_ITEM_TYPES: tuple[str, ...] = tuple(
    dict.fromkeys((*_PRD10_OBJECT_TYPES, *_LEGACY_SEARCH_ITEM_TYPES))
)

_SEARCH_ITEM_TYPE_VALUES = ", ".join(
    f"'{t}'" for t in _ALLOWED_SEARCH_ITEM_TYPES
)


class SearchIndex(Base):
    """PRD10 §5.14 SearchDocument (kept on the legacy ``search_indices`` table).

    Backward compatible with PRD4 ingestion writes:

    * ``item_type`` / ``item_id`` are the existing physical columns; PRD10
      callers should use the ``object_type`` / ``object_id`` aliases.
    * ``user_id`` / ``workspace_id`` / ``summary`` / ``embedding_id`` are new
      PRD10 columns and are **nullable** so the existing
      ``SearchService.index_item`` write path (which does not yet pass
      ``user_id``) continues to function.
    * The ``check_search_item_type`` constraint name is preserved.
    """

    __tablename__ = "search_indices"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Indexed object reference (PRD10: object_type / object_id)
    item_type = Column(String(50), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # PRD10 §5.14 owner scoping. Nullable for backwards compatibility with the
    # existing ingestion pipeline that does not yet pass user_id.
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    workspace_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Search content
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    content = Column(Text)
    tags = Column(JSON, default=list)  # List[str]
    search_metadata = Column(JSON, default=dict)  # Additional metadata for filtering

    # Vector embedding storage. ``embedding`` is the legacy inline JSON vector
    # (kept for the existing embedding service); ``embedding_id`` is the PRD10
    # §5.14 reference to a separate embeddings store.
    embedding = Column(JSON, nullable=True)
    embedding_id = Column(String(64), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Table constraints
    __table_args__ = (
        Index('ix_search_item_type_id', 'item_type', 'item_id'),
        Index('ix_search_created_at', 'created_at'),
        # PRD10 §21 advised composite index for user-scoped search.
        Index(
            'idx_search_user_object_updated',
            'user_id',
            'item_type',
            'updated_at',
        ),
        CheckConstraint(
            f"item_type IN ({_SEARCH_ITEM_TYPE_VALUES})",
            name='check_search_item_type'
        ),
    )

    @property
    def object_type(self) -> str:
        """PRD10 §5.14 alias for ``item_type``."""

        return self.item_type

    @property
    def object_id(self) -> uuid.UUID:
        """PRD10 §5.14 alias for ``item_id``."""

        return self.item_id

    def to_prd10_dict(self) -> dict:
        """Serialize to PRD10 §5.14 SearchDocument DTO."""

        return {
            "id": str(self.id),
            "user_id": str(self.user_id) if self.user_id else None,
            "workspace_id": (
                str(self.workspace_id) if self.workspace_id else None
            ),
            "object_type": self.item_type,
            "object_id": str(self.item_id) if self.item_id else None,
            "title": self.title,
            "summary": self.summary,
            "content": self.content,
            "tags": list(self.tags or []),
            "embedding_id": self.embedding_id,
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }

    def __repr__(self):
        return f"<SearchIndex({self.item_type}:{self.item_id})>"


class IngestionJob(Base):
    """数据引入任务 - 记录外部内容抓取

    Tracks the process of ingesting external content from URLs, PDFs, etc.
    into the system, including status tracking and error handling.
    """

    __tablename__ = "ingestion_jobs"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source information
    source_url = Column(String(500), nullable=True)
    source_type = Column(String(50), nullable=False)  # 'url', 'pdf', 'markdown'
    source_file_path = Column(String(500), nullable=True)

    # Processing status
    status = Column(String(20), default='pending', index=True)  # pending, running, completed, failed

    # Processing parameters
    chunk_size = Column(Integer, default=1000)  # Text chunking size in characters
    overlap = Column(Integer, default=200)  # Overlap between chunks in characters

    # Results
    items_created = Column(Integer, default=0)
    item_ids = Column(JSON, default=list)  # List[str] - IDs of created items

    # Error information
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # User reference (using String(36) for compatibility)
    created_by = Column(String(36), nullable=True, index=True)

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name='check_ingestion_status'
        ),
        CheckConstraint(
            "source_type IN ('url', 'pdf', 'markdown')",
            name='check_ingestion_source_type'
        ),
    )

    def __repr__(self):
        return f"<IngestionJob({self.source_type}:{self.status})>"


class InsightCluster(Base):
    """洞察聚类 - 对数据的聚合分析结果

    Stores aggregated insights and analysis results generated from
    existing data, such as summaries, trends, and topic clusters.
    """

    __tablename__ = "stage4_insight_clusters"  # Renamed to avoid conflict with insights.models

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Cluster information
    cluster_type = Column(String(50), nullable=False, index=True)  # 'summary', 'trend', 'topic', 'pattern'
    name = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)

    # Source data
    source_item_type = Column(String(50), nullable=True)  # 'card', 'task', etc.
    source_item_ids = Column(JSON, default=list)  # List[str]
    date_range = Column(JSON, nullable=True)  # {"start": "...", "end": "..."}

    # Insight output
    insight_data = Column(JSON, nullable=False)  # Specific insight content
    confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    sample_count = Column(Integer, nullable=True)  # Number of data points

    # Metadata
    parameters = Column(JSON, default=dict)  # Generation parameters
    generated_by = Column(String(36), nullable=True)  # User UUID
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "cluster_type IN ('summary', 'trend', 'topic', 'pattern')",
            name='check_insight_cluster_type'
        ),
    )

    def __repr__(self):
        return f"<InsightCluster({self.cluster_type}:{self.name})>"
