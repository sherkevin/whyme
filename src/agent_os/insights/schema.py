"""Insight Schemas - Request/Response Models for API."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================================
# Insight Schemas
# ============================================================================

class InsightCreate(BaseModel):
    """创建 Insight 请求"""
    workspace_id: str = Field(..., description="工作空间 ID")
    creator_id: str = Field(..., description="创建者 ID")
    claim: str = Field(..., description="洞察陈述", min_length=10, max_length=1000)
    rationale: Optional[str] = Field(None, description="推理过程")
    implications: Optional[List[str]] = Field(default_factory=list, description="启示列表")
    source_refs: Optional[List[str]] = Field(default_factory=list, description="来源 Item IDs")
    area_id: Optional[str] = Field(None, description="区域 ID")


class InsightResponse(BaseModel):
    """Insight 响应"""
    id: str = Field(..., description="Item ID")
    claim: str = Field(..., description="洞察陈述")
    rationale: Optional[str] = Field(None, description="推理过程")
    implications: List[str] = Field(default_factory=list, description="启示列表")
    claim_hash: str = Field(..., description="Claim Hash (用于去重)")
    source_refs: List[str] = Field(default_factory=list, description="来源 Item IDs")
    confidence_score: Optional[Dict[str, Any]] = Field(None, description="置信度分数")
    review_status: str = Field(..., description="审核状态")
    created_at: datetime = Field(..., description="创建时间")

    class Config:
        from_attributes = True


class InsightList(BaseModel):
    """Insight 列表响应"""
    insights: List[InsightResponse] = Field(default_factory=list)
    total: int = Field(..., description="总数")
    limit: int = Field(..., description="返回数量限制")
    offset: int = Field(..., description="偏移量")


class InsightReviewRequest(BaseModel):
    """审核 Insight 请求"""
    review_status: str = Field(..., description="审核状态: approved, rejected")
    reviewed_by: str = Field(..., description="审核者 ID")


# ============================================================================
# Insight Mining Schemas
# ============================================================================

class MineInsightRequest(BaseModel):
    """挖掘 Insight 请求"""
    workspace_id: str = Field(..., description="工作空间 ID")
    item_ids: List[str] = Field(..., description="Item ID 列表", min_length=3)


class MineInsightResponse(BaseModel):
    """挖掘 Insight 响应"""
    status: str = Field(..., description="状态: success, duplicate, error")
    insight_id: Optional[str] = Field(None, description="Insight ID")
    claim: Optional[str] = Field(None, description="洞察陈述")
    claim_hash: Optional[str] = Field(None, description="Claim Hash")
    error: Optional[str] = Field(None, description="错误信息")


class ClusterInfo(BaseModel):
    """集群信息"""
    id: str = Field(..., description="集群 ID")
    cluster_type: str = Field(..., description="集群类型")
    item_ids: List[str] = Field(..., description="Item IDs")
    mining_status: str = Field(..., description="挖掘状态")
    created_at: datetime = Field(..., description="创建时间")


class FindClustersRequest(BaseModel):
    """查找集群请求"""
    workspace_id: str = Field(..., description="工作空间 ID")
    min_cluster_size: int = Field(3, description="最小集群大小", ge=2)
    min_connection_weight: float = Field(0.7, description="最小连接权重", ge=0.0, le=1.0)


class FindClustersResponse(BaseModel):
    """查找集群响应"""
    clusters: List[ClusterInfo] = Field(default_factory=list)
    total: int = Field(..., description="集群数量")


# ============================================================================
# Insight Stats Schemas
# ============================================================================

class InsightStats(BaseModel):
    """Insight 统计信息"""
    total_insights: int = Field(..., description="总 Insight 数量")
    by_status: Dict[str, int] = Field(default_factory=dict, description="按状态统计")
    recent_insights: List[Dict[str, Any]] = Field(default_factory=list, description="最近的 Insights")


# ============================================================================
# Common Schemas
# ============================================================================

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态")
    service: str = Field(..., description="服务名称")
