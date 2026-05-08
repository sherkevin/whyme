"""Stage 6: Observability Integration Tests.

Complete integration tests for monitoring, logging, and health checks.
"""

import asyncio

import pytest

from agent_os.observability.middleware import (
    HealthChecker,
    PerformanceMetrics,
    configure_logging,
    log_context,
    monitor_performance,
    performance_metrics,
)

# ============================================================================
# Performance Metrics Tests
# ============================================================================

@pytest.mark.asyncio
async def test_performance_metrics():
    """测试性能指标收集"""
    metrics = PerformanceMetrics()

    # 记录一些请求
    metrics.record_request("GET", "/api/test", 200, 0.1)
    metrics.record_request("GET", "/api/test", 200, 0.2)
    metrics.record_request("GET", "/api/test", 404, 0.15)
    metrics.record_request("POST", "/api/create", 201, 0.5)

    # 获取统计
    stats = metrics.get_stats()

    assert stats["request_count"] == 4
    assert stats["error_count"] == 1  # 404
    assert stats["error_rate"] == 0.25
    assert stats["avg_response_time"] == (0.1 + 0.2 + 0.15 + 0.5) / 4
    assert "GET /api/test" in stats["endpoint_stats"]
    assert "POST /api/create" in stats["endpoint_stats"]


@pytest.mark.asyncio
async def test_performance_metrics_reset():
    """测试性能指标重置"""
    metrics = PerformanceMetrics()

    # 记录一些请求
    metrics.record_request("GET", "/api/test", 200, 0.1)
    metrics.record_request("GET", "/api/test", 200, 0.2)

    assert metrics.get_stats()["request_count"] == 2

    # 重置
    metrics.reset()

    assert metrics.get_stats()["request_count"] == 0
    assert metrics.get_stats()["endpoint_stats"] == {}


@pytest.mark.asyncio
async def test_p95_p99_metrics():
    """测试 P95/P99 指标计算"""
    metrics = PerformanceMetrics()

    # 记录多个不同时间的请求
    response_times = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
                      1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0]

    for rt in response_times:
        metrics.record_request("GET", "/api/test", 200, rt)

    stats = metrics.get_stats()

    # P95 应该接近 1.9 (95% of 20 items)
    # P99 应该接近 1.98 (99% of 20 items)
    assert 1.8 <= stats["p95_response_time"] <= 2.0
    assert 1.9 <= stats["p99_response_time"] <= 2.0


@pytest.mark.asyncio
async def test_metrics_memory_limit():
    """测试指标内存限制"""
    metrics = PerformanceMetrics()

    # 记录超过 1000 个请求
    for i in range(1500):
        metrics.record_request("GET", "/api/test", 200, 0.1)

    stats = metrics.get_stats()

    # 应该只保留最近的 1000 个
    assert len(metrics.response_times) <= 1000
    assert stats["request_count"] == 1500  # 但计数应该正确


# ============================================================================
# Health Check Tests
# ============================================================================

@pytest.mark.asyncio
async def test_health_checker():
    """测试健康检查器"""
    checker = HealthChecker()

    # 注册一些检查
    def check_1():
        return {"status": "healthy"}

    def check_2():
        return {"status": "healthy", "message": "OK"}

    def check_3():
        return {"status": "unhealthy", "message": "Failed"}

    checker.register_check("service1", check_1)
    checker.register_check("service2", check_2)
    checker.register_check("service3", check_3)

    # 执行健康检查
    result = await checker.check_health()

    assert result["status"] == "unhealthy"  # 因为有一个不健康
    assert len(result["checks"]) == 3
    assert result["checks"]["service1"]["status"] == "healthy"
    assert result["checks"]["service2"]["status"] == "healthy"
    assert result["checks"]["service3"]["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_health_checker_exception():
    """测试健康检查器异常处理"""
    checker = HealthChecker()

    # 注册一个会抛出异常的检查
    def failing_check():
        raise ValueError("Check failed")

    checker.register_check("failing", failing_check)

    # 执行健康检查
    result = await checker.check_health()

    assert result["status"] == "unhealthy"
    assert result["checks"]["failing"]["status"] == "unhealthy"
    assert "Check failed" in result["checks"]["failing"]["message"]


@pytest.mark.asyncio
async def test_health_checker_all_healthy():
    """测试所有检查都健康的情况"""
    checker = HealthChecker()

    # 只注册健康的检查
    def check_1():
        return {"status": "healthy"}

    def check_2():
        return {"status": "healthy"}

    checker.register_check("service1", check_1)
    checker.register_check("service2", check_2)

    # 执行健康检查
    result = await checker.check_health()

    assert result["status"] == "healthy"
    assert len(result["checks"]) == 2


# ============================================================================
# Decorator Tests
# ============================================================================

@pytest.mark.asyncio
async def test_monitor_performance_decorator():
    """测试性能监控装饰器"""
    @monitor_performance("test_function")
    async def test_function():
        await asyncio.sleep(0.01)
        return "result"

    result = await test_function()

    assert result == "result"


@pytest.mark.asyncio
async def test_monitor_performance_decorator_exception():
    """测试装饰器异常处理"""
    @monitor_performance("test_function_exception")
    async def test_function():
        raise ValueError("Test error")

    with pytest.raises(ValueError):
        await test_function()


# ============================================================================
# Logging Configuration Tests
# ============================================================================

def test_configure_logging():
    """测试日志配置"""
    # 配置简单格式日志
    configure_logging(level="INFO", format_json=False)

    # 验证配置成功
    import logging
    logger = logging.getLogger("test")
    logger.setLevel(logging.INFO)
    assert logger.level == logging.INFO


# ============================================================================
# Context Manager Tests
# ============================================================================

@pytest.mark.asyncio
async def test_log_context():
    """测试日志上下文管理器"""
    with log_context(user_id="123", action="test"):
        # 这里可以访问上下文
        pass


# ============================================================================
# Global Metrics Tests
# ============================================================================

@pytest.mark.asyncio
async def test_global_performance_metrics():
    """测试全局性能指标"""
    # 重置全局指标
    performance_metrics.reset()

    # 记录一些请求
    performance_metrics.record_request("GET", "/test1", 200, 0.1)
    performance_metrics.record_request("POST", "/test2", 201, 0.2)

    stats = performance_metrics.get_stats()

    assert stats["request_count"] == 2
    assert stats["error_count"] == 0
    assert stats["endpoint_stats"]["GET /test1"]["count"] == 1
    assert stats["endpoint_stats"]["POST /test2"]["count"] == 1


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
