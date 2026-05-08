"""Observability Module - Stage 6 Implementation.

Monitoring, logging, and performance tracking.
"""

import logging
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any, Dict, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ============================================================================
# Request ID Tracking
# ============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Request ID 追踪中间件

    为每个请求生成唯一的 request_id，并在日志中追踪
    """

    async def dispatch(self, request: Request, call_next):
        # 生成或获取 request_id
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # 注入到 request state
        request.state.request_id = request_id

        # 记录请求开始
        start_time = time.time()

        # 处理请求
        response = await call_next(request)

        # 计算处理时间
        process_time = time.time() - start_time

        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(process_time)

        # 记录日志
        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time": process_time
            }
        )

        return response


@contextmanager
def log_context(**kwargs):
    """
    日志上下文管理器 (简化版本)

    用法:
        with log_context(user_id="123", action="create_item"):
            # 你的代码
            pass

    注意: 这是一个简化版本，生产环境应该使用 contextvars
    """
    # 简化版本 - 只记录日志，不实际使用上下文变量
    logger.info(f"Log context: {kwargs}")

    # 创建一个简单的上下文对象
    class SimpleContext:
        def __init__(self, data):
            self.data = data

    context = SimpleContext(kwargs)

    try:
        yield context
    finally:
        pass


# ============================================================================
# Performance Monitoring
# ============================================================================

class PerformanceMetrics:
    """
    性能指标收集器

    收集 API 性能指标:
    - 响应时间
    - 请求数量
    - 错误率
    """

    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.response_times = []
        self.endpoint_stats = {}

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        response_time: float
    ):
        """记录请求"""
        self.request_count += 1

        if status_code >= 400:
            self.error_count += 1

        # 记录响应时间
        self.response_times.append(response_time)

        # 限制内存使用 - 只保留最近 1000 个
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]

        # 记录端点统计
        endpoint = f"{method} {path}"
        if endpoint not in self.endpoint_stats:
            self.endpoint_stats[endpoint] = {
                "count": 0,
                "errors": 0,
                "total_time": 0.0,
                "max_time": 0.0
            }

        stats = self.endpoint_stats[endpoint]
        stats["count"] += 1
        stats["total_time"] += response_time
        stats["max_time"] = max(stats["max_time"], response_time)

        if status_code >= 400:
            stats["errors"] += 1

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        if not self.response_times:
            return {
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate": 0.0,
                "avg_response_time": 0.0,
                "p95_response_time": 0.0,
                "p99_response_time": 0.0,
                "endpoint_stats": self.endpoint_stats
            }

        sorted_times = sorted(self.response_times)

        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / self.request_count if self.request_count > 0 else 0.0,
            "avg_response_time": sum(self.response_times) / len(self.response_times),
            "p95_response_time": sorted_times[int(len(sorted_times) * 0.95)] if len(sorted_times) > 0 else 0.0,
            "p99_response_time": sorted_times[int(len(sorted_times) * 0.99)] if len(sorted_times) > 0 else 0.0,
            "endpoint_stats": self.endpoint_stats
        }

    def reset(self):
        """重置统计"""
        self.request_count = 0
        self.error_count = 0
        self.response_times = []
        self.endpoint_stats = {}


# 全局性能指标实例
performance_metrics = PerformanceMetrics()


# ============================================================================
# Performance Monitoring Middleware
# ============================================================================

class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    性能监控中间件

    自动收集请求性能指标
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # 处理请求
        response = await call_next(request)

        # 计算处理时间
        process_time = time.time() - start_time

        # 记录指标
        performance_metrics.record_request(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            response_time=process_time
        )

        return response


# ============================================================================
# Logging Configuration
# ============================================================================

def configure_logging(
    level: str = "INFO",
    format_json: bool = False
):
    """
    配置日志系统

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        format_json: 是否使用 JSON 格式
    """
    import logging.config

    if format_json:
        # JSON 格式日志 (适合 ELK 解析)
        log_format = {
            "version": 1,
            "timestamp": "%(asctime)s",
            "level": "%(levelname)s",
            "name": "%(name)s",
            "message": "%(message)s",
            "request_id": "%(request_id)s",
            "process_time": "%(process_time)s"
        }
    else:
        # 简单格式日志
        log_format = (
            "[%(asctime)s] %(levelname)s [%(name)s] "
            "%(message)s [request_id=%(request_id)s] "
            "[process_time=%(process_time)s]"
        )

    logging.basicConfig(
        level=getattr(logging, level),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S"
    )


# ============================================================================
# Decorators for Monitoring
# ============================================================================

def monitor_performance(func_name: str | None = None):
    """
    性能监控装饰器

    用法:
        @monitor_performance("my_function")
        async def my_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        func_name_str = func_name or func.__name__

        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)

                # 记录成功
                logger.info(
                    f"Function completed: {func_name_str}",
                    extra={
                        "function": func_name_str,
                        "duration": time.time() - start_time,
                        "status": "success"
                    }
                )

                return result

            except Exception as e:
                # 记录失败
                logger.error(
                    f"Function failed: {func_name_str}",
                    extra={
                        "function": func_name_str,
                        "duration": time.time() - start_time,
                        "status": "error",
                        "error": str(e)
                    }
                )

                raise

        return wrapper
    return decorator


# ============================================================================
# Health Check
# ============================================================================

class HealthChecker:
    """
    健康检查器

    检查系统各组件的健康状态
    """

    def __init__(self):
        self.checks = {}

    def register_check(
        self,
        name: str,
        check_func: Callable[[], dict[str, Any]]
    ):
        """
        注册健康检查

        Args:
            name: 检查名称
            check_func: 检查函数，返回 {"status": "healthy"|"unhealthy", "message": "..."}
        """
        self.checks[name] = check_func

    async def check_health(self) -> dict[str, Any]:
        """
        执行所有健康检查

        Returns:
            健康状态字典
        """
        results = {}
        overall_healthy = True

        for name, check_func in self.checks.items():
            try:
                result = check_func()
                results[name] = result

                if result.get("status") != "healthy":
                    overall_healthy = False

            except Exception as e:
                results[name] = {
                    "status": "unhealthy",
                    "message": str(e)
                }
                overall_healthy = False

        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "checks": results,
            "timestamp": time.time()
        }


# 全局健康检查器实例
health_checker = HealthChecker()
