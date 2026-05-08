"""Pydantic schemas for Stage 4 API requests and responses."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# =============================================================================
# Search Index Schemas
# =============================================================================

class SearchIndexCreate(BaseModel):
    """Schema for creating/updating a search index."""
    item_type: str = Field(..., description="Type of item (card, task, note, etc.)")
    item_id: str = Field(..., description="UUID of the item")
    title: str = Field(..., min_length=1, description="Item title")
    content: str | None = Field(None, description="Item content")
    tags: list[str] = Field(default_factory=list, description="Search tags")
    search_metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    embedding: list[float] | None = Field(None, description="Vector embedding")


class SearchIndexUpdate(BaseModel):
    """Schema for updating a search index."""
    title: str | None = Field(None, min_length=1)
    content: str | None = None
    tags: list[str] | None = None
    search_metadata: dict[str, Any] | None = None
    embedding: list[float] | None = None


class SearchIndexResponse(BaseModel):
    """Schema for search index response."""
    id: uuid.UUID
    item_type: str
    item_id: uuid.UUID
    title: str
    content: str | None = None
    tags: list[str]
    search_metadata: dict[str, Any]
    embedding: list[float] | None = None
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


# =============================================================================
# Search Query Schemas
# =============================================================================

class SearchQueryRequest(BaseModel):
    """Schema for search query."""
    query: str = Field(..., min_length=1, description="Search query text")
    item_types: list[str] | None = Field(
        None,
        description="Filter by item types (card, task, note, etc.)"
    )
    tags: list[str] | None = Field(None, description="Filter by tags")
    date_from: datetime | None = Field(None, description="Filter from date")
    date_to: datetime | None = Field(None, description="Filter to date")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Results per page")
    sort_by: str = Field(
        default="relevance",
        description="Sort by: relevance, date, -date"
    )
    include_vectors: bool = Field(default=False, description="Include vector embeddings")


class SearchResultItemResponse(BaseModel):
    """Schema for a single search result."""
    item_type: str
    item_id: str
    title: str
    content_snippet: str
    score: float
    tags: list[str]
    search_metadata: dict[str, Any]
    created_at: datetime


class SearchResponse(BaseModel):
    """Schema for search results."""
    total: int = Field(..., description="Total matching results")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Results per page")
    results: list[SearchResultItemResponse]


class BulkIndexRequest(BaseModel):
    """Schema for bulk indexing."""
    items: list[SearchIndexCreate] = Field(..., min_items=1, max_items=100)


class BulkIndexResponse(BaseModel):
    """Schema for bulk index response."""
    indexed: int = Field(..., description="Number of items indexed")
    failed: int = Field(..., description="Number of items that failed")
    errors: list[str] = Field(default_factory=list, description="Error messages")


# =============================================================================
# Ingestion Job Schemas
# =============================================================================

class IngestionJobCreate(BaseModel):
    """Schema for creating an ingestion job."""
    source_type: str = Field(..., description="Source type: url, pdf, markdown")
    source_url: str | None = Field(None, description="URL to ingest")
    source_file_path: str | None = Field(None, description="Local file path")
    chunk_size: int = Field(default=1000, ge=100, le=10000, description="Chunk size")
    overlap: int = Field(default=200, ge=0, le=1000, description="Chunk overlap")


class IngestionJobResponse(BaseModel):
    """Schema for ingestion job response."""
    id: uuid.UUID
    source_type: str
    source_url: str | None = None
    source_file_path: str | None = None
    status: str
    chunk_size: int
    overlap: int
    items_created: int
    item_ids: list[str]
    error_message: str | None = None
    error_stack: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: str | None = None

    class Config:
        from_attributes = True


class IngestionJobListResponse(BaseModel):
    """Schema for ingestion job list."""
    total: int
    jobs: list[IngestionJobResponse]


# =============================================================================
# Insight Cluster Schemas
# =============================================================================

class InsightClusterCreate(BaseModel):
    """Schema for creating an insight cluster."""
    cluster_type: str = Field(
        ...,
        description="Type: summary, trend, topic, pattern"
    )
    name: str | None = Field(None, max_length=200)
    description: str | None = Field(None)
    source_item_type: str | None = Field(None)
    source_item_ids: list[str] | None = Field(None)
    date_range: dict[str, str] | None = Field(None)
    insight_data: dict[str, Any] = Field(..., description="Insight content")
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    sample_count: int | None = Field(None, ge=0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = Field(None)


class InsightClusterResponse(BaseModel):
    """Schema for insight cluster response."""
    id: uuid.UUID
    cluster_type: str
    name: str | None = None
    description: str | None = None
    source_item_type: str | None = None
    source_item_ids: list[str]
    date_range: dict[str, str] | None = None
    insight_data: dict[str, Any]
    confidence: float | None = None
    sample_count: int | None = None
    parameters: dict[str, Any]
    generated_by: str | None = None
    generated_at: datetime
    expires_at: datetime | None = None

    class Config:
        from_attributes = True


class InsightClusterListResponse(BaseModel):
    """Schema for insight cluster list."""
    total: int
    insights: list[InsightClusterResponse]


# =============================================================================
# Rebuild Index Schema
# =============================================================================

class RebuildIndexResponse(BaseModel):
    """Schema for index rebuild response."""
    status: str
    message: str
    total_indexed: int
    duration_seconds: float | None = None
