"""Today module schemas for API requests and responses."""

import uuid
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============== Today View Schemas ==============

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


# ============== Today Insight Schemas ==============

class InsightSource(BaseModel):
    """A source item for an insight."""
    id: uuid.UUID = Field(..., description="Source item ID")
    title: Optional[str] = Field(None, description="Source item title")
    item_type: str = Field(..., description="Type of source item")

    model_config = ConfigDict(from_attributes=True)


class DailyInsightResponse(BaseModel):
    """Response for daily insight endpoint.

    Structured insight data for rendering with required fields:
    - claim: Main claim/statement
    - rationale: Reasoning/explanation
    - implications: List of implications
    - sources: Supporting source items
    """
    id: uuid.UUID = Field(..., description="Insight ID")
    claim: str = Field(..., description="Main claim/statement of the insight")
    rationale: str = Field(..., description="Reasoning/explanation")
    implications: List[str] = Field(..., description="List of implications")
    level: int = Field(..., ge=1, le=3, description="Insight level (1-3)")
    status: str = Field(..., description="Insight status")
    evidence_count: int = Field(..., description="Number of evidence items")
    sources: List[InsightSource] = Field(
        default_factory=list,
        description="Source items supporting this insight"
    )
    created_at: datetime = Field(..., description="Insight creation time")
    updated_at: datetime = Field(..., description="Last update time")

    model_config = ConfigDict(from_attributes=True)


class TodayInsightListResponse(BaseModel):
    """Response for today insights list endpoint."""
    data: List[DailyInsightResponse] = Field(..., description="List of insights")
    day: str = Field(..., description="Date in YYYY-MM-DD format")
    total: int = Field(..., description="Total count")


# ============== Error Schemas ==============

class TodayErrorResponse(BaseModel):
    """Error response."""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Application-specific error code")
