"""Observability Schemas - Request/Response Models for API."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# ============================================================================
# Metrics Schemas
# ============================================================================

class EndpointStats(BaseModel):
    """端点统计"""
    endpoint: str = Field(..., description="端点路径")
    count: int = Field(..., description="请求总数")
    errors: int = Field(..., description="错误数")
    avg_time: float = Field(..., description="平均响应时间 (秒)")
    max_time: float = Field(..., description="最大响应时间 (秒)")


class MetricsResponse(BaseModel):
    """性能指标响应"""
    request_count: int = Field(..., description="总请求数")
    error_count: int = Field(..., description="总错误数")
    error_rate: float = Field(..., description="错误率")
    avg_response_time: float = Field(..., description="平均响应时间 (秒)")
    p95_response_time: float = Field(..., description="P95 响应时间 (秒)")
    p99_response_time: float = Field(..., description="P99 响应时间 (秒)")
    endpoint_stats: List[EndpointStats] = Field(default_factory=list, description="端点统计")


# ============================================================================
# Health Check Schemas
# ============================================================================

class HealthCheck(BaseModel):
    """单个健康检查结果"""
    status: str = Field(..., description="状态: healthy, unhealthy")
    message: Optional[str] = Field(None, description="消息")


class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="整体状态: healthy, unhealthy")
    checks: Dict[str, HealthCheck] = Field(default_factory=dict, description="各项检查结果")
    timestamp: float = Field(..., description="检查时间戳")


class HealthResponse(BaseModel):
    """简单健康检查响应"""
    status: str = Field(..., description="服务状态")
    service: str = Field(..., description="服务名称")


# ============================================================================
# System Info Schemas
# ============================================================================

class SystemInfo(BaseModel):
    """系统信息"""
    service: str = Field(..., description="服务名称")
    version: str = Field(..., description="版本号")
    environment: str = Field(..., description="运行环境")
    system: Dict[str, Any] = Field(default_factory=dict, description="系统资源")
    timestamp: float = Field(..., description="时间戳")
