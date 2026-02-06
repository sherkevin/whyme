"""Today module schemas for API requests and responses."""

import uuid
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============== Response Schemas ==============

class TodayItem(BaseModel):
    """An item in the Today view."""
    id: uuid.UUID
    type: str
    title: Optional[str]
    content: Optional[str]
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    source_type: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class TodayViewResponse(BaseModel):
    """Today view response.

    Aggregates items that need user attention today:
    - Active tasks
    - Recent notes
    - Items requiring follow-up
    """
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    items: List[TodayItem]
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics (total items, by type, by status)"
    )
    generated_at: datetime = Field(default_factory=datetime.now)


# ============== Error Schemas ==============

class TodayErrorResponse(BaseModel):
    """Error response."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Application-specific error code")
