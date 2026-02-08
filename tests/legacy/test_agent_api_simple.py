"""Simple tests for Agent API endpoints (Stage 2).

Basic tests to verify API endpoints are accessible.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from agent_os.db.base import Base
from agent_os.db.session import get_db
from tests.test_app import test_app as app


@pytest.fixture
async def in_memory_db():
    """Create in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest.fixture
async def db_session(in_memory_db):
    """Create async database session for testing."""
    async_session_maker = async_sessionmaker(
        bind=in_memory_db,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_maker() as session:
        yield session


@pytest.fixture
def test_client(db_session):
    """Create test client with database session override."""
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Override both get_db functions (from db.base and db.session)
    from agent_os.db import base as db_base
    app.dependency_overrides[db_base.get_db] = override_get_db
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


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
