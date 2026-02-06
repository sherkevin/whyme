"""Connection API Schemas - Request/Response Models."""

import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Connection Schemas
# ============================================================================

class ConnectionEdge(BaseModel):
    """连接边"""
    id: uuid.UUID
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    weight: float = Field(..., ge=0.0, le=1.0, description="连接权重 (0.0 - 1.0)")
    relation_type: str = Field(..., description="关系类型: topic, causal, supplement")
    is_strong: bool = Field(..., description="是否为强连接")
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class ConnectionList(BaseModel):
    """连接列表"""
    node_id: uuid.UUID
    connections: List[ConnectionEdge]
    total_count: int
    strong_count: int

    class Config:
        from_attributes = True


class ConnectionStats(BaseModel):
    """连接统计"""
    total_connections: int
    outgoing_connections: int
    incoming_connections: int
    strong_connections: int
    by_type: dict[str, int]


class GraphNode(BaseModel):
    """图节点"""
    id: uuid.UUID
    label: str = Field(..., description="节点标签 (通常是title)")
    type: str = Field(..., description="节点类型: note, task, resource, etc.")
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class GraphEdgeSimple(BaseModel):
    """简单图边 (用于可视化)"""
    from_node: uuid.UUID
    to_node: uuid.UUID
    weight: float
    relation_type: str
    is_strong: bool


class GraphData(BaseModel):
    """图数据 (用于可视化)"""
    nodes: List[GraphNode]
    edges: List[GraphEdgeSimple]


class RecalculateRequest(BaseModel):
    """手动触发连接计算请求"""
    item_id: uuid.UUID
    limit: Optional[int] = Field(100, ge=1, le=1000, description="候选Item数量限制")


class RecalculateResponse(BaseModel):
    """重新计算响应"""
    item_id: uuid.UUID
    connections_created: int
    connections_updated: int
    message: str
