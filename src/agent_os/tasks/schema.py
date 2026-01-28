"""Pydantic schemas for Task management."""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Task Schemas
# =============================================================================

class TaskBase(BaseModel):
    """Base task schema with common fields."""

    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    type: str = Field("task", pattern="^(task|habit|goal)$", description="Task type")
    source: str = Field("manual", pattern="^(manual|ai_generated|recurring)$", description="Task source")
    status: str = Field("pending", pattern="^(pending|in_progress|completed)$", description="Task status")
    priority: int = Field(5, ge=1, le=10, description="Task priority (1-10)")
    scheduled_date: Optional[date] = Field(None, description="Scheduled date for the task")


class TaskCreate(TaskBase):
    """Schema for creating a new task."""

    pass


class TaskUpdate(BaseModel):
    """Schema for updating a task."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    type: Optional[str] = Field(None, pattern="^(task|habit|goal)$")
    source: Optional[str] = Field(None, pattern="^(manual|ai_generated|recurring)$")
    status: Optional[str] = Field(None, pattern="^(pending|in_progress|completed)$")
    priority: Optional[int] = Field(None, ge=1, le=10)
    scheduled_date: Optional[date] = None
    completed_at: Optional[datetime] = None


class TaskResponse(TaskBase):
    """Schema for task response."""

    id: int
    user_id: int
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskList(BaseModel):
    """Schema for task list response with pagination."""

    items: List[TaskResponse]
    total: int
    page: int = 1
    page_size: int = 20


class TaskStatusUpdate(BaseModel):
    """Schema for updating task status."""

    status: str = Field(..., pattern="^(pending|in_progress|completed)$")
    completed_at: Optional[datetime] = None


# =============================================================================
# Today's Tasks Aggregation Schemas
# =============================================================================

class TaskStats(BaseModel):
    """Schema for task statistics."""

    total: int = 0
    pending: int = 0
    in_progress: int = 0
    completed: int = 0
    by_priority: dict = Field(default_factory=dict)  # {1: count, 2: count, ...}
    by_type: dict = Field(default_factory=dict)  # {task: count, habit: count, goal: count}


class TodayTasksResponse(BaseModel):
    """Schema for today's tasks aggregation response."""

    date: date
    tasks: List[TaskResponse]
    stats: TaskStats
    knowledge_context: Optional[dict] = None  # Context from knowledge base


class TaskBatchCreate(BaseModel):
    """Schema for batch creating tasks."""

    tasks: List[TaskCreate] = Field(..., min_length=1, max_length=50)


class TaskBatchUpdate(BaseModel):
    """Schema for batch updating tasks."""

    task_ids: List[int] = Field(..., min_length=1, max_length=50)
    updates: TaskUpdate


# =============================================================================
# Task Query Schemas
# =============================================================================

class TaskQueryParams(BaseModel):
    """Schema for task query parameters."""

    status: Optional[str] = Field(None, pattern="^(pending|in_progress|completed)$")
    type: Optional[str] = Field(None, pattern="^(task|habit|goal)$")
    priority_min: Optional[int] = Field(None, ge=1, le=10)
    priority_max: Optional[int] = Field(None, ge=1, le=10)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    sort_by: str = Field("created_at", pattern="^(created_at|updated_at|scheduled_date|priority|completed_at)$")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
