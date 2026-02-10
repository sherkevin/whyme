"""Data models for Stage 4 - Search, Ingestion, and Insight."""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Text, Boolean, Integer, Float, JSON, DateTime, Index, CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from agent_os.db.base import Base


class SearchIndex(Base):
    """统一搜索索引 - 支持多类型数据检索

    Provides unified search across multiple data types (Card, Task, Note, etc.)
    with both full-text search and optional vector search capabilities.
    """

    __tablename__ = "search_indices"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Indexed object reference
    item_type = Column(String(50), nullable=False, index=True)
    item_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Search content
    title = Column(Text, nullable=False)
    content = Column(Text)
    tags = Column(JSON, default=list)  # List[str]
    search_metadata = Column(JSON, default=dict)  # Additional metadata for filtering (renamed to avoid conflict)

    # Vector embedding (optional, for semantic search)
    embedding = Column(JSON, nullable=True)  # Array[float] or vector type

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Table constraints
    __table_args__ = (
        Index('ix_search_item_type_id', 'item_type', 'item_id'),
        Index('ix_search_created_at', 'created_at'),
        CheckConstraint(
            "item_type IN ('card', 'task', 'note', 'decision_point', 'workspace', 'project', 'resource', 'test')",
            name='check_search_item_type'
        ),
    )

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
