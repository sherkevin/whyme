"""Test Configuration and Fixtures for PRD4 Tests."""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# PRD10 SQLite UUID compatibility. The legacy ORM models declare primary
# keys with ``postgresql.UUID(as_uuid=True)``; SQLAlchemy 2.x has no default
# DDL rendering for that type on SQLite, which is the dialect used by
# ``TEST_DATABASE_URL`` below. Importing this module side-effect-installs a
# ``@compiles`` rule that renders PG UUID as ``CHAR(32)`` only on the SQLite
# dialect, so ``Workspace.__table__.create(connection)`` etc. work in tests
# without rewriting the model layer. PostgreSQL DDL is unchanged.
import agent_os.db.sqlite_compat  # noqa: F401

# Import agent models
from agent_os.agent.models import AgentProcessEvent

# Import auth models
from agent_os.auth.models import APIKey, AuditLog, Role, Session, User, UserRole

# Import base after models to avoid circular imports
# Import garden models (PRD7)
from agent_os.garden.models import DailyInsight, KnowledgeCardLink
from agent_os.inbox.prd10_models import Prd10InboxItem

# Import only PRD4 models (avoid knowledge models that reference User/Organization)
from agent_os.items.models import (
    Area,
    DecisionPoint,
    GraphEdge,
    Item,
    LedgerEvent,
    Project,
    TaskExtension,
    Workspace,
)
from agent_os.jobs.models import Job as Prd10Job
from agent_os.kb.models import Chunk as Prd10Chunk
from agent_os.kb.models import Document as Prd10Document

# Import PRD10 tables that ``cards`` references via FK (kb_folders, kb_documents,
# kb_chunks, prd10_inbox_items, prd10_sources, prd10_jobs). Without these the
# Card.__table__.create call below fails with NoReferencedTableError now that
# the Card model has been extended with PRD10 §5.5 columns (folder_id,
# inbox_item_id, source_id).
from agent_os.kb.models import Folder as Prd10Folder

# Import knowledge models
from agent_os.knowledge.models import Card
from agent_os.notifications.models import Notification as Prd10Notification

# Import search_engine (stage4) models
# Note: Renamed InsightCluster to InsightCluster4 to avoid conflicts with old insights module
from agent_os.search_engine.models import IngestionJob, SearchIndex
from agent_os.search_engine.models import InsightCluster as InsightCluster4
from agent_os.sources.models import Source as Prd10Source

# Import stage3 models
from agent_os.stage3.models import AgentDecision, Skill, TaskExecutionLog

# Create a list of PRD4 tables for testing
PRD4_TABLES = [
    'workspaces', 'areas', 'projects', 'items',
    'task_extensions', 'decision_points', 'ledger_events', 'graph_edges',
    # Note: 'insight_extensions', 'insight_clusters' removed - old insights module deprecated
    'users', 'api_keys', 'sessions', 'roles', 'user_roles', 'audit_logs',
    'agent_process_events',
    'cards',
    'agent_decisions',  # Stage 3
    'skills',  # Stage 3
    'task_execution_logs',  # Stage 3
    'search_indices',  # Stage 4 / search_engine
    'ingestion_jobs',  # Stage 4 / search_engine
    'stage4_insight_clusters',  # Stage 4 / search_engine
    'knowledge_card_links',  # PRD7 Garden
    'daily_insights'  # PRD7 Garden
]


# ============================================================================
# Test Database Configuration
# ============================================================================

# Default to per-process in-memory SQLite + StaticPool. The previous
# default (``sqlite+aiosqlite:///./test.db``) shared a single file across
# every test's engine fixture, which caused intermittent
# ``OperationalError: no such table`` cross-talk when tests with
# function-scoped engines (PRD10 tests) ran alongside this fixture's
# function-scoped engine, and produced cleanup-time PermissionError on
# Windows. ``:memory:`` gives each engine instance its own DB; StaticPool
# is required so multiple connections within the same engine see the
# same DB. Set ``TEST_DATABASE_URL`` to override (e.g. real Postgres).
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)
_USE_STATIC_POOL = TEST_DATABASE_URL.startswith("sqlite+aiosqlite:///:memory:")


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def engine():
    """创建测试数据库引擎"""
    from sqlalchemy.pool import StaticPool

    engine_kwargs: dict = {
        "echo": False,
        "future": True,
    }
    if _USE_STATIC_POOL:
        engine_kwargs["poolclass"] = StaticPool
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        engine_kwargs["poolclass"] = NullPool

    engine = create_async_engine(TEST_DATABASE_URL, **engine_kwargs)

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
            # Note: Old insights module (InsightExtension, InsightCluster) deprecated
            # Using search_engine InsightCluster instead (see below)
            # Auth tables
            User.__table__.create(connection, checkfirst=True)
            APIKey.__table__.create(connection, checkfirst=True)
            Session.__table__.create(connection, checkfirst=True)
            Role.__table__.create(connection, checkfirst=True)
            UserRole.__table__.create(connection, checkfirst=True)
            AuditLog.__table__.create(connection, checkfirst=True)
            # Agent tables
            AgentProcessEvent.__table__.create(connection, checkfirst=True)
            # PRD10 tables that the Card model FKs to. Created BEFORE Card
            # so the FK references resolve. Order: source -> inbox_item ->
            # folder -> document -> chunk (forward chain).
            Prd10Source.__table__.create(connection, checkfirst=True)
            Prd10InboxItem.__table__.create(connection, checkfirst=True)
            Prd10Folder.__table__.create(connection, checkfirst=True)
            Prd10Document.__table__.create(connection, checkfirst=True)
            Prd10Chunk.__table__.create(connection, checkfirst=True)
            Prd10Job.__table__.create(connection, checkfirst=True)
            Prd10Notification.__table__.create(connection, checkfirst=True)
            # Knowledge tables
            Card.__table__.create(connection, checkfirst=True)
            # Stage 3 tables
            AgentDecision.__table__.create(connection, checkfirst=True)
            Skill.__table__.create(connection, checkfirst=True)
            TaskExecutionLog.__table__.create(connection, checkfirst=True)
            # Stage 4 tables
            SearchIndex.__table__.create(connection, checkfirst=True)
            IngestionJob.__table__.create(connection, checkfirst=True)
            InsightCluster4.__table__.create(connection, checkfirst=True)
            # PRD7 Garden tables
            KnowledgeCardLink.__table__.create(connection, checkfirst=True)
            DailyInsight.__table__.create(connection, checkfirst=True)

        def drop_prd4_tables(connection):
            # Drop auth tables first (foreign key dependencies)
            AuditLog.__table__.drop(connection, checkfirst=True)
            UserRole.__table__.drop(connection, checkfirst=True)
            Role.__table__.drop(connection, checkfirst=True)
            Session.__table__.drop(connection, checkfirst=True)
            APIKey.__table__.drop(connection, checkfirst=True)
            User.__table__.drop(connection, checkfirst=True)
            # Drop Stage 4 tables
            InsightCluster4.__table__.drop(connection, checkfirst=True)
            IngestionJob.__table__.drop(connection, checkfirst=True)
            SearchIndex.__table__.drop(connection, checkfirst=True)
            # Drop PRD7 Garden tables
            DailyInsight.__table__.drop(connection, checkfirst=True)
            KnowledgeCardLink.__table__.drop(connection, checkfirst=True)
            # Drop Stage 3 tables
            TaskExecutionLog.__table__.drop(connection, checkfirst=True)
            Skill.__table__.drop(connection, checkfirst=True)
            AgentDecision.__table__.drop(connection, checkfirst=True)
            # Drop PRD4 tables
            # Note: Old insights module (InsightExtension, InsightCluster) deprecated
            # Already dropped via search_engine InsightCluster4 above
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

    # 清理数据 - 删除所有测试数据。
    # ``engine`` is per-test in-memory + StaticPool by default, so the whole
    # database is discarded when the engine is disposed at the end of the
    # ``engine`` fixture. The DELETE loop below is kept for the rare case
    # where ``TEST_DATABASE_URL`` overrides to a real Postgres / file-backed
    # SQLite. Every statement is wrapped in try/except so a missing table
    # (e.g. if a test rolled back the schema) doesn't poison the next test.
    from sqlalchemy import delete
    from sqlalchemy.exc import OperationalError, ProgrammingError

    async with async_session_maker() as session:
        for model in (
            KnowledgeCardLink,
            DailyInsight,
            InsightCluster4,
            IngestionJob,
            SearchIndex,
            TaskExecutionLog,
            Skill,
            AgentDecision,
            Card,
            AgentProcessEvent,
            UserRole,
            AuditLog,
            User,
            APIKey,
            Session,
            Role,
            Item,
            Project,
            Area,
            Workspace,
        ):
            try:
                await session.execute(delete(model))
            except (OperationalError, ProgrammingError):
                await session.rollback()
        try:
            await session.commit()
        except (OperationalError, ProgrammingError):
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
