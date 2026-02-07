"""Pydantic schemas for Stage 3 API requests and responses."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


# =============================================================================
# Decision Schemas
# =============================================================================

class DecisionOption(BaseModel):
    """Schema for a decision option."""
    id: str = Field(..., description="Option ID")
    title: str = Field(..., description="Option title")
    description: str = Field(..., description="Option description")
    rationale: str = Field(..., description="Rationale for this option")
    risks: List[str] = Field(default_factory=list, description="Associated risks")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")


class DecisionCreate(BaseModel):
    """Schema for creating a decision (used internally)."""
    task_id: str = Field(..., description="Task ID")
    step_name: str = Field(..., description="Step name")
    options: List[DecisionOption] = Field(..., min_items=1, description="Decision options")


class DecisionResponse(BaseModel):
    """Schema for decision response."""
    id: uuid.UUID
    task_id: str
    step_name: str
    options: List[DecisionOption]
    selected_option_id: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DecisionConfirm(BaseModel):
    """Schema for confirming a decision."""
    selected_option_id: str = Field(..., description="ID of selected option")
    confirmed_by: Optional[str] = Field(None, description="User ID confirming")


# =============================================================================
# Skill Schemas
# =============================================================================

class SkillStep(BaseModel):
    """Schema for a skill step."""
    order: int = Field(..., ge=1, description="Step order")
    name: str = Field(..., description="Step name")
    description: Optional[str] = Field(None, description="Step description")
    agent_action: str = Field(..., description="Agent action to execute")
    requires_confirmation: bool = Field(default=False, description="Needs user confirmation")


class SkillCreate(BaseModel):
    """Schema for creating a skill."""
    name: str = Field(..., min_length=1, max_length=200, description="Skill name")
    description: str = Field(..., min_length=1, description="Skill description")
    category: str = Field(..., description="Skill category")
    steps: List[SkillStep] = Field(..., min_items=1, description="Skill steps")
    applicable_item_types: List[str] = Field(
        default_factory=list,
        description="Item types this skill applies to"
    )
    required_tags: List[str] = Field(
        default_factory=list,
        description="Tags required for skill to apply"
    )
    version: str = Field(default="1.0", description="Skill version")


class SkillUpdate(BaseModel):
    """Schema for updating a skill."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = None
    steps: Optional[List[SkillStep]] = None
    applicable_item_types: Optional[List[str]] = None
    required_tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class SkillResponse(BaseModel):
    """Schema for skill response."""
    id: uuid.UUID
    name: str
    description: str
    category: str
    steps: List[Dict[str, Any]]  # Stored as JSON in DB
    applicable_item_types: List[str]
    required_tags: List[str]
    version: str
    parent_skill_id: Optional[uuid.UUID] = None
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SkillRecommendRequest(BaseModel):
    """Schema for skill recommendation request."""
    task_type: str = Field(..., description="Task item type")
    task_tags: Optional[List[str]] = Field(None, description="Task tags")
    task_content: Optional[str] = Field(None, description="Task content")
    limit: int = Field(default=5, ge=1, le=20, description="Max recommendations")


class SkillRecommendation(BaseModel):
    """Schema for skill recommendation."""
    skill: SkillResponse
    score: float = Field(..., ge=0.0, le=1.0, description="Match score")
    match_reason: str = Field(..., description="Why this skill was recommended")


# =============================================================================
# Flow Execution Schemas
# =============================================================================

class FlowStartRequest(BaseModel):
    """Schema for starting a flow."""
    task_id: str = Field(..., description="Task ID")
    skill_id: str = Field(..., description="Skill ID to execute")
    initial_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Initial context for the flow"
    )


class FlowStartResponse(BaseModel):
    """Schema for flow start response."""
    execution_id: str
    task_id: str
    skill_id: str
    status: str
    current_step: int


class FlowStatusResponse(BaseModel):
    """Schema for flow status response."""
    execution_id: str
    status: str
    current_step: int
    total_steps: int
    decision: Optional[DecisionResponse] = None


class FlowContinueRequest(BaseModel):
    """Schema for continuing a flow."""
    decision_id: str = Field(..., description="Decision ID")
    selected_option_id: str = Field(..., description="Selected option ID")


class FlowPauseResponse(BaseModel):
    """Schema for flow pause response."""
    execution_id: str
    status: str
    message: str = "Flow paused"


class FlowResumeResponse(BaseModel):
    """Schema for flow resume response."""
    execution_id: str
    status: str
    message: str = "Flow resumed"


# =============================================================================
# Execution Log Schemas
# =============================================================================

class ExecutionLogResponse(BaseModel):
    """Schema for execution log response."""
    id: uuid.UUID
    task_id: str
    step_name: str
    step_order: int
    status: str
    agent_action: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    decision_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True
