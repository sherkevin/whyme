"""Tests for Agent API endpoints (Stage 2).

PRD10 NOTICE
============

The Stage 2 ``agent`` router (``/api/v1/agent/process``, ``/api/v1/agent/items/...``)
predates PRD10. PRD10 wraps agentic behavior under
``agent_os.ai.router`` (Mydow AI) and the Skills run path. Additionally,
``TestClient(app=app)`` no longer works under httpx 0.28.

Skipped at collection time.
"""

import pytest

pytest.skip(
    "Legacy Stage 2 agent API tests; superseded by Mydow AI + Skills PRD10 routers.",
    allow_module_level=True,
)

from fastapi.testclient import TestClient  # noqa: E402,F401
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402,F401

from agent_os.items import crud as item_crud  # noqa: E402,F401
from agent_os.items.models import Item, ItemStatus  # noqa: E402,F401
from agent_os.server.app import app  # noqa: E402,F401

# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def agent_test_client(db_session):
    """Create test client with database session override."""
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Override get_db dependency
    from agent_os.db.dependencies import get_db

    from agent_os import db as db_module

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[db_module.get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# =============================================================================
# Test Agent Tick Endpoint
# =============================================================================

class TestAgentTickEndpoint:
    """测试 POST /api/v1/agent/tick 端点"""

    def test_agent_tick_with_no_items(
        self,
        agent_test_client: TestClient,
        test_token_headers: dict
    ):
        """验证没有 raw items 时的 tick"""
        response = agent_test_client.post(
            "/api/v1/agent/tick",
            json={"max_items": 10},
            headers=test_token_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["processed"] == 0
        assert data["succeeded"] == 0
        assert data["failed"] == 0
        assert data["skipped"] == 0
        assert data["results"] == []

        print("✅ Agent tick with no items returns empty results")

    def test_agent_tick_with_raw_items(
        self,
        agent_test_client: TestClient,
        test_token_headers: dict,
        db_session: AsyncSession,
        test_user
    ):
        """验证处理 raw items"""
        # 创建 3 个 raw items
        for i in range(3):
            item_crud.create_item_sync(db_session, {
                "user_id": test_user.id,
                "workspace_id": test_user.default_workspace_id,
                "content": f"Task {i}: Complete this item",
                "status": ItemStatus.RAW
            })

        db_session.commit()

        # 调用 agent tick
        response = agent_test_client.post(
            "/api/v1/agent/tick",
            json={"max_items": 10},
            headers=test_token_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["processed"] == 3
        assert data["succeeded"] == 3
        assert data["failed"] == 0
        assert len(data["results"]) == 3

        # 验证每个结果
        for result in data["results"]:
            assert result["success"] is True
            assert result["from_status"] == "raw"
            assert result["to_status"] == "processed"
            assert result["title"] is not None
            assert result["item_type"] is not None

        print("✅ Agent tick processed 3 items successfully")

    def test_agent_tick_respects_max_items(
        self,
        agent_test_client: TestClient,
        test_token_headers: dict,
        db_session: AsyncSession,
        test_user
    ):
        """验证 max_items 参数限制"""
        # 创建 10 个 raw items
        for i in range(10):
            item_crud.create_item_sync(db_session, {
                "user_id": test_user.id,
                "workspace_id": test_user.default_workspace_id,
                "content": f"Task {i}",
                "status": ItemStatus.RAW
            })

        db_session.commit()

        # 只处理 5 个
        response = agent_test_client.post(
            "/api/v1/agent/tick",
            json={"max_items": 5},
            headers=test_token_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["processed"] == 5
        assert data["succeeded"] == 5

        print("✅ Max items limit respected")

    def test_agent_tick_requires_authentication(
        self,
        agent_test_client: TestClient
    ):
        """验证需要认证"""
        response = agent_test_client.post(
            "/api/v1/agent/tick",
            json={"max_items": 10}
        )

        assert response.status_code == 401

        print("✅ Authentication required")


# =============================================================================
# Test Process Item Endpoint
# =============================================================================

class TestProcessItemEndpoint:
    """测试 POST /api/v1/agent/process/{item_id} 端点"""

    def test_process_raw_item(
        self,
        agent_test_client: TestClient,
        test_token_headers: dict,
        db_session: AsyncSession,
        test_user
    ):
        """验证处理单个 raw item"""
        # 创建一个 raw item
        item = item_crud.create_item_sync(db_session, {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "content": "TODO: Implement feature X",
            "status": ItemStatus.RAW
        })

        db_session.commit()
        item_id = str(item.id)

        # 处理 item
        response = agent_test_client.post(
            f"/api/v1/agent/process/{item_id}",
            json={"force_reprocess": False},
            headers=test_token_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["item_id"] == item_id
        assert data["from_status"] == "raw"
        assert data["to_status"] == "processed"
        assert data["title"] is not None
        assert data["item_type"] == "task"

        print("✅ Single item processed successfully")

    def test_process_nonexistent_item(
        self,
        agent_test_client: TestClient,
        test_token_headers: dict
    ):
        """验证处理不存在的 item"""
        response = agent_test_client.post(
            "/api/v1/agent/process/nonexistent-id",
            json={"force_reprocess": False},
            headers=test_token_headers
        )

        # 应该返回成功，但 success=False
        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert "not found" in data["error"].lower()

        print("✅ Nonexistent item handled gracefully")

    def test_process_item_requires_authentication(
        self,
        agent_test_client: TestClient,
        db_session: AsyncSession,
        test_user
    ):
        """验证需要认证"""
        # 创建一个 item
        item = item_crud.create_item_sync(db_session, {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "content": "Test",
            "status": ItemStatus.RAW
        })
        db_session.commit()

        response = agent_test_client.post(
            f"/api/v1/agent/process/{item.id}",
            json={"force_reprocess": False}
        )

        assert response.status_code == 401

        print("✅ Authentication required")


# =============================================================================
# Test Agent Status Endpoint
# =============================================================================

class TestAgentStatusEndpoint:
    """测试 GET /api/v1/agent/status 端点"""

    def test_get_agent_status(
        self,
        agent_test_client: TestClient,
        test_token_headers: dict
    ):
        """验证获取 agent 状态"""
        response = agent_test_client.get(
            "/api/v1/agent/status",
            headers=test_token_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "raw_count" in data
        assert "processed_count" in data
        assert "recent_raw_items" in data
        assert isinstance(data["recent_raw_items"], list)

        print("✅ Agent status retrieved")

    def test_get_agent_status_requires_authentication(
        self,
        agent_test_client: TestClient
    ):
        """验证需要认证"""
        response = agent_test_client.get("/api/v1/agent/status")

        assert response.status_code == 401

        print("✅ Authentication required")


# =============================================================================
# Test Execution
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Agent API Endpoints for Stage 2")
    print("=" * 60)
    print()

    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
