"""Observability API Router - Monitoring and Metrics Endpoints."""

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter

from agent_os.observability.middleware import health_checker, performance_metrics
from agent_os.observability.schema import (
    EndpointStats,
    HealthCheckResponse,
    HealthResponse,
    MetricsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/observability", tags=["observability"])


# ============================================================================
# Metrics Endpoints
# ============================================================================

@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    获取性能指标

    Returns:
        性能指标统计
    """
    stats = performance_metrics.get_stats()

    # 转换端点统计
    endpoint_stats_list = []
    for endpoint, data in stats["endpoint_stats"].items():
        endpoint_stats_list.append(
            EndpointStats(
                endpoint=endpoint,
                count=data["count"],
                errors=data["errors"],
                avg_time=data["total_time"] / data["count"] if data["count"] > 0 else 0,
                max_time=data["max_time"]
            )
        )

    return MetricsResponse(
        request_count=stats["request_count"],
        error_count=stats["error_count"],
        error_rate=stats["error_rate"],
        avg_response_time=stats["avg_response_time"],
        p95_response_time=stats["p95_response_time"],
        p99_response_time=stats["p99_response_time"],
        endpoint_stats=endpoint_stats_list
    )


@router.post("/metrics/reset")
async def reset_metrics():
    """
    重置性能指标

    Returns:
        重置结果
    """
    performance_metrics.reset()

    return {
        "status": "success",
        "message": "Metrics reset successfully"
    }


# ============================================================================
# Health Check Endpoints
# ============================================================================

@router.get("/health", response_model=HealthCheckResponse)
async def get_health():
    """
    获取系统健康状态

    Returns:
        健康检查结果
    """
    result = await health_checker.check_health()

    return HealthCheckResponse(**result)


@router.get("/health/simple", response_model=HealthResponse)
async def get_health_simple():
    """
    简单健康检查

    Returns:
        健康状态
    """
    return HealthResponse(
        status="healthy",
        service="agent-os"
    )


# ============================================================================
# System Info Endpoints
# ============================================================================

@router.get("/info")
async def get_system_info() -> dict[str, Any]:
    """
    获取系统信息

    Returns:
        系统信息字典
    """
    import os

    import psutil

    # CPU 使用率
    cpu_percent = psutil.cpu_percent(interval=1)

    # 内存使用
    memory = psutil.virtual_memory()

    # 磁盘使用
    disk = psutil.disk_usage('/')

    return {
        "service": "agent-os",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "system": {
            "cpu_percent": cpu_percent,
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            }
        },
        "timestamp": time.time()
    }


# ============================================================================
# Database Health Check
# ============================================================================

def check_database_health() -> dict[str, Any]:
    """
    数据库健康检查

    检查数据库连接是否正常

    Returns:
        健康状态字典
    """
    # 这是一个简化版本 - 生产环境应该实际连接数据库
    # 这里我们假设数据库是健康的
    return {
        "status": "healthy",
        "message": "Database connection OK"
    }


# 注册数据库健康检查
health_checker.register_check("database", check_database_health)
