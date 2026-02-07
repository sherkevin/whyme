"""Simple tests for Agent API endpoints (Stage 2).

Basic tests to verify API endpoints are accessible.
"""

import pytest
from fastapi.testclient import TestClient

from agent_os.server.app import app


@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)


class TestAgentAPIEndpoints:
    """Basic tests for Agent API endpoints"""

    def test_agent_tick_endpoint_exists(self, test_client):
        """验证 /api/v1/agent/tick 端点存在"""
        response = test_client.post("/api/v1/agent/tick", json={"max_items": 10})

        # 应该返回 401 (需要认证)，而不是 404
        assert response.status_code in [401, 422]
        print("✅ /api/v1/agent/tick endpoint exists")

    def test_process_item_endpoint_exists(self, test_client):
        """验证 /api/v1/agent/process/{item_id} 端点存在"""
        response = test_client.post("/api/v1/agent/process/test-id", json={"force_reprocess": False})

        # 应该返回 401 (需要认证)，而不是 404
        assert response.status_code in [401, 422]
        print("✅ /api/v1/agent/process/{item_id} endpoint exists")

    def test_agent_status_endpoint_exists(self, test_client):
        """验证 /api/v1/agent/status 端点存在"""
        response = test_client.get("/api/v1/agent/status")

        # 应该返回 401 (需要认证)，而不是 404
        assert response.status_code == 401
        print("✅ /api/v1/agent/status endpoint exists")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
