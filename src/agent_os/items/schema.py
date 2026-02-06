"""Unified Items Schemas - PRD4 API contracts."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import uuid


class ItemType(str, Enum):
    """Item 类型枚举"""
    NOTE = "note"
    TASK = "task"
    RESOURCE = "resource"
    PLAN = "plan"
    INSIGHT = "insight"


class ItemStatus(str, Enum):
    """Item 状态枚举"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class RiskLevel(str, Enum):
    """风险级别枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExecutionStatus(str, Enum):
    """执行状态枚举"""
    DRAFT = "draft"
    PLANNING = "planning"
    DECISION = "decision"
    EXECUTING = "executing"
    DONE = "done"


class RelationType(str, Enum):
    """关系类型枚举"""
    TOPIC = "topic"
    CAUSAL = "causal"
    SUPPLEMENT = "supplement"


# ============================================================================
# Workspace Schemas
# ============================================================================

class WorkspaceBase(BaseModel):
    """Workspace 基础 Schema"""
    name: str = Field(..., max_length=200)
    description: Optional[str] = None


class WorkspaceCreate(WorkspaceBase):
    """创建 Workspace"""
    owner_id: uuid.UUID


class WorkspaceResponse(WorkspaceBase):
    """Workspace 响应"""
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Area Schemas
# ============================================================================

class AreaBase(BaseModel):
    """Area 基础 Schema"""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=7, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: Optional[str] = Field(None, max_length=50)
    parent_id: Optional[uuid.UUID] = None
    sort_order: int = 0


class AreaCreate(AreaBase):
    """创建 Area"""
    workspace_id: uuid.UUID


class AreaResponse(AreaBase):
    """Area 响应"""
    id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Project Schemas
# ============================================================================

class ProjectBase(BaseModel):
    """Project 基础 Schema"""
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    status: str = "active"
    area_id: Optional[uuid.UUID] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ProjectCreate(ProjectBase):
    """创建 Project"""
    workspace_id: uuid.UUID


class ProjectResponse(ProjectBase):
    """Project 响应"""
    id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Item Schemas
# ============================================================================

class ItemBase(BaseModel):
    """Item 基础 Schema"""
    type: ItemType
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    area_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None
    source_type: Optional[str] = None
    source_meta: Dict[str, Any] = Field(default_factory=dict)
    status: ItemStatus = ItemStatus.ACTIVE


class ItemCreate(ItemBase):
    """创建 Item"""
    workspace_id: uuid.UUID
    creator_id: uuid.UUID


class ItemUpdate(BaseModel):
    """更新 Item"""
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    area_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None
    status: Optional[ItemStatus] = None


class ItemResponse(ItemBase):
    """Item 响应"""
    id: uuid.UUID
    workspace_id: uuid.UUID
    creator_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ItemListResponse(BaseModel):
    """Item 列表响应"""
    items: List[ItemResponse]
    total: int
    page: int
    page_size: int


# ============================================================================
# Task Extension Schemas
# ============================================================================

class TaskExtensionBase(BaseModel):
    """Task Extension 基础 Schema"""
    goal: Optional[str] = None
    constraints: Optional[str] = None
    risk_level: RiskLevel = RiskLevel.LOW
    execution_status: ExecutionStatus = ExecutionStatus.DRAFT


class TaskExtensionCreate(TaskExtensionBase):
    """创建 Task Extension"""
    item_id: uuid.UUID


class TaskExtensionResponse(TaskExtensionBase):
    """Task Extension 响应"""
    id: uuid.UUID
    item_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Decision Point Schemas
# ============================================================================

class DecisionPointBase(BaseModel):
    """Decision Point 基础 Schema"""
    task_id: uuid.UUID
    type: str = Field(..., pattern=r'^(selection|info|boundary)$')
    options: List[Dict[str, Any]] = Field(default_factory=list)


class DecisionPointCreate(DecisionPointBase):
    """创建 Decision Point"""
    pass


class DecisionPointResponse(DecisionPointBase):
    """Decision Point 响应"""
    id: uuid.UUID
    user_choice: Optional[uuid.UUID] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DecisionConfirm(BaseModel):
    """确认决策"""
    option_id: uuid.UUID


# ============================================================================
# Ledger Event Schemas
# ============================================================================

class LedgerEventBase(BaseModel):
    """Ledger Event 基础 Schema"""
    task_id: uuid.UUID
    event_type: str = Field(..., pattern=r'^(agent_suggested|user_confirmed|deliverable_generated)$')
    snapshot: Dict[str, Any] = Field(default_factory=dict)


class LedgerEventCreate(LedgerEventBase):
    """创建 Ledger Event"""
    pass


class LedgerEventResponse(LedgerEventBase):
    """Ledger Event 响应"""
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Graph Edge Schemas
# ============================================================================

class GraphEdgeBase(BaseModel):
    """Graph Edge 基础 Schema"""
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    weight: float = Field(ge=0.0, le=1.0, default=0.0)
    relation_type: RelationType
    is_strong: bool = False


class GraphEdgeCreate(GraphEdgeBase):
    """创建 Graph Edge"""
    pass


class GraphEdgeResponse(GraphEdgeBase):
    """Graph Edge 响应"""
    id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


class GraphConnectionResponse(BaseModel):
    """连接查询响应"""
    node_id: uuid.UUID
    connections: List[GraphEdgeResponse]
    strong_count: int


class GraphPathResponse(BaseModel):
    """路径查询响应"""
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    path: List[uuid.UUID]
    length: int
