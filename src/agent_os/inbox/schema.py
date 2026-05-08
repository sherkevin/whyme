"""Inbox module schemas for API requests and responses."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

# ============== Request Schemas ==============

class InboxItemCreate(BaseModel):
    """Create a new inbox item.

    Inbox items are raw inputs that haven't been processed yet.
    They can be notes, tasks, or resources collected from various sources.
    """
    workspace_id: uuid.UUID = Field(..., description="Workspace ID")
    title: str | None = Field(None, max_length=500, description="Item title")
    content: str | None = Field(None, description="Item content/description")
    source_type: str = Field(
        default="manual",
        description="Source type: manual, wechat, chrome_extension, etc."
    )
    source_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Source metadata (URL, sender, etc.)"
    )
    type: str = Field(
        default="note",
        description="Item type: note, task, resource"
    )


class InboxItemUpdate(BaseModel):
    """Update an inbox item."""
    title: str | None = Field(None, max_length=500)
    content: str | None = None
    type: str | None = None


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
    title: str | None
    content: str | None
    summary: str | None
    source_type: str | None
    source_meta: dict[str, Any]
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
    status: str | None = Field(None, description="Filter by status")
    type: str | None = Field(None, description="Filter by type")
    source_type: str | None = Field(None, description="Filter by source type")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    search: str | None = Field(None, description="Search in title and content")


# ============== Error Schemas ==============

class InboxErrorResponse(BaseModel):
    """Error response."""
    detail: str = Field(..., description="Error message")
    error_code: str | None = Field(None, description="Application-specific error code")
