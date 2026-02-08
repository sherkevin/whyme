"""Agent API integration tests (Stage 2).

Tests for Agent API endpoints using the test database infrastructure.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.items.models import Item, ItemStatus, Workspace
from agent_os.auth.models import User
from tests.test_app import test_app as app


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def agent_test_client(db_session):
    """Create test client with database session override."""
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Override get_db dependencies
    from agent_os.db import base as db_base
    from agent_os.db.session import get_db as session_get_db

    app.dependency_overrides[db_base.get_db] = override_get_db
    app.dependency_overrides[session_get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user_with_workspace(db_session: AsyncSession):
    """Create a test user with workspace."""
    import uuid
    from agent_os.auth.security import get_password_hash

    # Create user with UUID
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        username="testuser",
        email="test@example.com",
        password_hash=get_password_hash("password123"),
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()

    # Create workspace with UUID
    workspace_id = uuid.uuid4()
    workspace = Workspace(
        id=workspace_id,
        name="Test Workspace",
        owner_id=user.id
    )
    db_session.add(workspace)
    await db_session.flush()

    # Update user's default workspace
    user.default_workspace_id = workspace_id

    await db_session.commit()
    await db_session.refresh(user)

    return {"user": user, "workspace": workspace}


@pytest.fixture
def test_token_headers(test_user_with_workspace):
    """Create test token headers."""
    from agent_os.auth.security import create_access_token

    user = test_user_with_workspace["user"]
    token = create_access_token(data={"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Agent Tick Endpoint Tests
# =============================================================================

class TestAgentTickEndpoint:
    """测试 POST /api/v1/agent/tick 端点"""

    def test_agent_tick_requires_authentication(self, agent_test_client):
        """验证需要认证"""
        response = agent_test_client.post(
            "/api/v1/agent/tick",
            json={"max_items": 10}
        )

        assert response.status_code == 401
        print("✅ Agent tick requires authentication")

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

        # Should succeed even with no items
        assert response.status_code == 200
        data = response.json()

        assert data["processed"] == 0
        assert data["succeeded"] == 0
        assert data["failed"] == 0
        assert data["skipped"] == 0
        assert data["results"] == []

        print("✅ Agent tick with no items returns empty results")


# =============================================================================
# Process Item Endpoint Tests
# =============================================================================

class TestProcessItemEndpoint:
    """测试 POST /api/v1/agent/process/{item_id} 端点"""

    def test_process_item_requires_authentication(self, agent_test_client):
        """验证需要认证"""
        response = agent_test_client.post(
            "/api/v1/agent/process/test-id",
            json={"force_reprocess": False}
        )

        assert response.status_code == 401
        print("✅ Process item requires authentication")


# =============================================================================
# Agent Status Endpoint Tests
# =============================================================================

class TestAgentStatusEndpoint:
    """测试 GET /api/v1/agent/status 端点"""

    def test_get_agent_status_requires_authentication(self, agent_test_client):
        """验证需要认证"""
        response = agent_test_client.get("/api/v1/agent/status")

        assert response.status_code == 401
        print("✅ Agent status requires authentication")

    def test_get_agent_status_with_auth(
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

        print("✅ Agent status retrieved successfully")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Agent API Integration for Stage 2")
    print("=" * 60)
    print()

    pytest.main([__file__, "-v", "--tb=short"])
