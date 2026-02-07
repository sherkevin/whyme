"""Inbox module schemas for API requests and responses."""

import uuid
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


# ============== Request Schemas ==============

class InboxItemCreate(BaseModel):
    """Create a new inbox item.

    Inbox items are raw inputs that haven't been processed yet.
    They can be notes, tasks, or resources collected from various sources.
    """
    workspace_id: uuid.UUID = Field(..., description="Workspace ID")
    title: Optional[str] = Field(None, max_length=500, description="Item title")
    content: Optional[str] = Field(None, description="Item content/description")
    source_type: str = Field(
        default="manual",
        description="Source type: manual, wechat, chrome_extension, etc."
    )
    source_meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source metadata (URL, sender, etc.)"
    )
    type: str = Field(
        default="note",
        description="Item type: note, task, resource"
    )


class InboxItemUpdate(BaseModel):
    """Update an inbox item."""
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    type: Optional[str] = None


class InboxItemStatusUpdate(BaseModel):
    """Update inbox item status.

    Status flow: raw -> processed -> archived
    """
    status: str = Field(
        ...,
        description="New status: raw, processed, active, archived, deleted"
    )


# ============== Response Schemas ==============

class InboxItemResponse(BaseModel):
    """Inbox item response."""
    id: uuid.UUID
    workspace_id: uuid.UUID
    creator_id: uuid.UUID
    type: str
    title: Optional[str]
    content: Optional[str]
    summary: Optional[str]
    source_type: Optional[str]
    source_meta: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InboxItemListResponse(BaseModel):
    """Paginated inbox item list response."""
    items: list[InboxItemResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# ============== Query Parameters ==============

class InboxItemListParams(BaseModel):
    """Query parameters for inbox item list."""
    status: Optional[str] = Field(None, description="Filter by status")
    type: Optional[str] = Field(None, description="Filter by type")
    source_type: Optional[str] = Field(None, description="Filter by source type")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    search: Optional[str] = Field(None, description="Search in title and content")


# ============== Error Schemas ==============

class InboxErrorResponse(BaseModel):
    """Error response."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Application-specific error code")
