"""Pydantic schemas for Knowledge management (Inbox and Cards)."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID


# =============================================================================
# Inbox Schemas
# =============================================================================

class InboxItemBase(BaseModel):
    """Base schema for InboxItem."""
    content: str = Field(..., min_length=1, max_length=10000, description="Inbox item content")
    source: Optional[str] = Field(default="manual", pattern="^(manual|api|import)$", description="Source of the item")
    extra_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class InboxItemCreate(InboxItemBase):
    """Schema for creating a new inbox item."""
    pass


class InboxItemUpdate(BaseModel):
    """Schema for updating an inbox item."""
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    status: Optional[str] = Field(None, pattern="^(raw|processed|archived)$")
    extra_data: Optional[Dict[str, Any]] = None


class InboxItemResponse(InboxItemBase):
    """Schema for inbox item response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime


class InboxItemList(BaseModel):
    """Schema for list of inbox items."""
    items: List[InboxItemResponse]
    total: int = Field(..., description="Total number of items")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# =============================================================================
# Card Schemas
# =============================================================================

class CardBase(BaseModel):
    """Base schema for Card."""
    title: str = Field(..., min_length=1, max_length=200, description="Card title")
    content: str = Field(..., min_length=1, max_length=10000, description="Card content")
    para_type: str = Field(..., pattern="^(concept|action|reference)$", description="Paragraph type")
    tags: Optional[List[str]] = Field(default_factory=list, description="Tags for the card")
    source_inbox_item_id: Optional[UUID] = Field(None, description="Source inbox item ID")


class CardCreate(CardBase):
    """Schema for creating a new card."""
    pass


class CardUpdate(BaseModel):
    """Schema for updating a card."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1, max_length=10000)
    para_type: Optional[str] = Field(None, pattern="^(concept|action|reference)$")
    tags: Optional[List[str]] = None


class CardResponse(CardBase):
    """Schema for card response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class CardWithSource(CardResponse):
    """Schema for card with source inbox item info."""
    source_item: Optional[InboxItemResponse] = None


class CardList(BaseModel):
    """Schema for list of cards."""
    items: List[CardResponse]
    total: int = Field(..., description="Total number of cards")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# =============================================================================
# Search Schemas (for RAG)
# =============================================================================

class SearchResultItem(BaseModel):
    """Schema for a single search result."""
    card_id: int
    title: str
    content: str
    para_type: str
    similarity: float = Field(..., ge=0.0, le=1.0, description="Similarity score")


class SearchResponse(BaseModel):
    """Schema for search response."""
    query: str
    results: List[SearchResultItem]
    total: int


class KnowledgeContextResponse(BaseModel):
    """Schema for knowledge context response."""
    task_description: str
    context_cards: List[SearchResultItem]
    total_cards: int
    formatted_context: str
