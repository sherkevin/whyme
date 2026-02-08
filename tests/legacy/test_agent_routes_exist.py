"""Simple Agent API route existence test (Stage 2).

This test verifies that the Agent API routes are registered without requiring database setup.
"""

import pytest


def test_agent_routes_registered():
    """验证 Agent API 路由已注册到 FastAPI 应用"""
    from tests.test_app import test_app as app

    # 获取所有路由
    all_routes = [route for route in app.routes if hasattr(route, 'path')]

    # 提取 Agent 相关路由
    agent_routes = [route.path for route in all_routes if '/agent/' in route.path]

    # 验证预期的路由存在
    expected_routes = [
        '/api/v1/agent/tick',
        '/api/v1/agent/process/{item_id}',
        '/api/v1/agent/status'
    ]

    for expected in expected_routes:
        assert expected in agent_routes, f"Expected route '{expected}' not found. Available agent routes: {agent_routes}"

    print(f"✅ All Agent API routes registered: {agent_routes}")


def test_agent_router_has_endpoints():
    """验证 Agent Router 有正确的端点"""
    from agent_os.agent.router import router

    # 获取路由中的所有端点
    routes = [route for route in router.routes if hasattr(route, 'path')]

    # 验证端点数量和类型
    assert len(routes) == 3, f"Expected 3 routes, found {len(routes)}"

    # 验证端点方法
    route_methods = {}
    for route in routes:
        if hasattr(route, 'methods'):
            route_methods[route.path] = route.methods

    assert 'POST' in route_methods.get('/api/v1/agent/tick', set())
    assert 'POST' in route_methods.get('/api/v1/agent/process/{item_id}', set())
    assert 'GET' in route_methods.get('/api/v1/agent/status', set())

    print("✅ Agent Router has correct endpoints with correct methods")


def test_agent_functions_exported():
    """验证 Agent 包导出所需函数"""
    from agent_os.agent import (
        agent_tick,
        process_inbox_item,
        ProcessingResult
    )

    # 验证函数存在
    assert callable(agent_tick), "agent_tick should be callable"
    assert callable(process_inbox_item), "process_inbox_item should be callable"

    # 验证 ProcessingResult 类存在
    assert ProcessingResult is not None, "ProcessingResult should be defined"

    print("✅ Agent package exports required functions and classes")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Agent API Route Registration for Stage 2")
    print("=" * 60)
    print()

    pytest.main([__file__, "-v"])
