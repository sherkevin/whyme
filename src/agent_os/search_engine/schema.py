"""Pydantic schemas for Stage 4 API requests and responses."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


# =============================================================================
# Search Index Schemas
# =============================================================================

class SearchIndexCreate(BaseModel):
    """Schema for creating/updating a search index."""
    item_type: str = Field(..., description="Type of item (card, task, note, etc.)")
    item_id: str = Field(..., description="UUID of the item")
    title: str = Field(..., min_length=1, description="Item title")
    content: Optional[str] = Field(None, description="Item content")
    tags: List[str] = Field(default_factory=list, description="Search tags")
    search_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")


class SearchIndexUpdate(BaseModel):
    """Schema for updating a search index."""
    title: Optional[str] = Field(None, min_length=1)
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    search_metadata: Optional[Dict[str, Any]] = None
    embedding: Optional[List[float]] = None


class SearchIndexResponse(BaseModel):
    """Schema for search index response."""
    id: uuid.UUID
    item_type: str
    item_id: uuid.UUID
    title: str
    content: Optional[str] = None
    tags: List[str]
    search_metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# Search Query Schemas
# =============================================================================

class SearchQueryRequest(BaseModel):
    """Schema for search query."""
    query: str = Field(..., min_length=1, description="Search query text")
    item_types: Optional[List[str]] = Field(
        None,
        description="Filter by item types (card, task, note, etc.)"
    )
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
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
    tags: List[str]
    search_metadata: Dict[str, Any]
    created_at: datetime


class SearchResponse(BaseModel):
    """Schema for search results."""
    total: int = Field(..., description="Total matching results")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Results per page")
    results: List[SearchResultItemResponse]


class BulkIndexRequest(BaseModel):
    """Schema for bulk indexing."""
    items: List[SearchIndexCreate] = Field(..., min_items=1, max_items=100)


class BulkIndexResponse(BaseModel):
    """Schema for bulk index response."""
    indexed: int = Field(..., description="Number of items indexed")
    failed: int = Field(..., description="Number of items that failed")
    errors: List[str] = Field(default_factory=list, description="Error messages")


# =============================================================================
# Ingestion Job Schemas
# =============================================================================

class IngestionJobCreate(BaseModel):
    """Schema for creating an ingestion job."""
    source_type: str = Field(..., description="Source type: url, pdf, markdown")
    source_url: Optional[str] = Field(None, description="URL to ingest")
    source_file_path: Optional[str] = Field(None, description="Local file path")
    chunk_size: int = Field(default=1000, ge=100, le=10000, description="Chunk size")
    overlap: int = Field(default=200, ge=0, le=1000, description="Chunk overlap")


class IngestionJobResponse(BaseModel):
    """Schema for ingestion job response."""
    id: uuid.UUID
    source_type: str
    source_url: Optional[str] = None
    source_file_path: Optional[str] = None
    status: str
    chunk_size: int
    overlap: int
    items_created: int
    item_ids: List[str]
    error_message: Optional[str] = None
    error_stack: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


class IngestionJobListResponse(BaseModel):
    """Schema for ingestion job list."""
    total: int
    jobs: List[IngestionJobResponse]


# =============================================================================
# Insight Cluster Schemas
# =============================================================================

class InsightClusterCreate(BaseModel):
    """Schema for creating an insight cluster."""
    cluster_type: str = Field(
        ...,
        description="Type: summary, trend, topic, pattern"
    )
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None)
    source_item_type: Optional[str] = Field(None)
    source_item_ids: Optional[List[str]] = Field(None)
    date_range: Optional[Dict[str, str]] = Field(None)
    insight_data: Dict[str, Any] = Field(..., description="Insight content")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    sample_count: Optional[int] = Field(None, ge=0)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    expires_at: Optional[datetime] = Field(None)


class InsightClusterResponse(BaseModel):
    """Schema for insight cluster response."""
    id: uuid.UUID
    cluster_type: str
    name: Optional[str] = None
    description: Optional[str] = None
    source_item_type: Optional[str] = None
    source_item_ids: List[str]
    date_range: Optional[Dict[str, str]] = None
    insight_data: Dict[str, Any]
    confidence: Optional[float] = None
    sample_count: Optional[int] = None
    parameters: Dict[str, Any]
    generated_by: Optional[str] = None
    generated_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InsightClusterListResponse(BaseModel):
    """Schema for insight cluster list."""
    total: int
    insights: List[InsightClusterResponse]


# =============================================================================
# Rebuild Index Schema
# =============================================================================

class RebuildIndexResponse(BaseModel):
    """Schema for index rebuild response."""
    status: str
    message: str
    total_indexed: int
    duration_seconds: Optional[float] = None
