"""Test Configuration and Fixtures for PRD4 Tests."""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import os
import uuid

# Import only PRD4 models (avoid knowledge models that reference User/Organization)
from agent_os.items.models import (
    Workspace, Area, Project, Item,
    TaskExtension, DecisionPoint, LedgerEvent, GraphEdge
)

# Import base after models to avoid circular imports
from agent_os.db.base import Base

# Create a list of PRD4 tables for testing
PRD4_TABLES = [
    'workspaces', 'areas', 'projects', 'items',
    'task_extensions', 'decision_points', 'ledger_events', 'graph_edges'
]


# ============================================================================
# Test Database Configuration
# ============================================================================

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///./test.db"
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
        future=True
    )

    # 只创建 PRD4 表 (避免 knowledge models 的依赖问题)
    async with engine.begin() as conn:
        def create_prd4_tables(connection):
            # 直接使用 SQLAlchemy Core 创建表
            Workspace.__table__.create(connection, checkfirst=True)
            Area.__table__.create(connection, checkfirst=True)
            Project.__table__.create(connection, checkfirst=True)
            Item.__table__.create(connection, checkfirst=True)
            TaskExtension.__table__.create(connection, checkfirst=True)
            DecisionPoint.__table__.create(connection, checkfirst=True)
            LedgerEvent.__table__.create(connection, checkfirst=True)
            GraphEdge.__table__.create(connection, checkfirst=True)

        def drop_prd4_tables(connection):
            GraphEdge.__table__.drop(connection, checkfirst=True)
            LedgerEvent.__table__.drop(connection, checkfirst=True)
            DecisionPoint.__table__.drop(connection, checkfirst=True)
            TaskExtension.__table__.drop(connection, checkfirst=True)
            Item.__table__.drop(connection, checkfirst=True)
            Project.__table__.drop(connection, checkfirst=True)
            Area.__table__.drop(connection, checkfirst=True)
            Workspace.__table__.drop(connection, checkfirst=True)

        # 先删除后创建
        await conn.run_sync(drop_prd4_tables)
        await conn.run_sync(create_prd4_tables)

    yield engine

    # 清理
    async with engine.begin() as conn:
        await conn.run_sync(drop_prd4_tables)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """创建数据库会话"""
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session

    # 清理数据
    async with async_session_maker() as session:
        await session.rollback()


# ============================================================================
# Helper Fixtures
# ============================================================================

@pytest.fixture
def sample_workspace_id() -> uuid.UUID:
    """示例 Workspace ID"""
    return uuid.uuid4()


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    """示例 User ID"""
    return uuid.uuid4()


@pytest.fixture
async def clean_db(db_session: AsyncSession):
    """清理数据库"""
    yield

    # Teardown: 删除所有测试数据
    await db_session.rollback()


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Pytest 配置"""
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "unit: mark test as unit test"
    )


# ============================================================================
# Test Data Builders
# ============================================================================

class TestDataBuilder:
    """测试数据构建器"""

    @staticmethod
    def build_workspace_data(**kwargs):
        """构建 Workspace 测试数据"""
        defaults = {
            "name": "Test Workspace",
            "description": "Test Description",
            "owner_id": uuid.uuid4()
        }
        defaults.update(kwargs)
        return defaults

    @staticmethod
    def build_area_data(workspace_id: uuid.UUID, **kwargs):
        """构建 Area 测试数据"""
        defaults = {
            "workspace_id": workspace_id,
            "name": "Test Area",
            "color": "#FF5733",
            "sort_order": 1
        }
        defaults.update(kwargs)
        return defaults

    @staticmethod
    def build_project_data(workspace_id: uuid.UUID, area_id: uuid.UUID = None, **kwargs):
        """构建 Project 测试数据"""
        defaults = {
            "workspace_id": workspace_id,
            "area_id": area_id,
            "name": "Test Project",
            "status": "active"
        }
        defaults.update(kwargs)
        return defaults

    @staticmethod
    def build_item_data(workspace_id: uuid.UUID, creator_id: uuid.UUID, **kwargs):
        """构建 Item 测试数据"""
        defaults = {
            "workspace_id": workspace_id,
            "creator_id": creator_id,
            "type": "note",
            "title": "Test Note",
            "content": "Test Content",
            "status": "active"
        }
        defaults.update(kwargs)
        return defaults


@pytest.fixture
def test_data_builder():
    """测试数据构建器 fixture"""
    return TestDataBuilder()
