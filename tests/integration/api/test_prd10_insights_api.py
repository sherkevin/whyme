"""PRD10 §12 Insights & Reports endpoint tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# §15.5: insights/summary now also queries AIConversation / AIMessage to compute
# the right-rail "AI 助理活跃度" panel — register their tables in Base.metadata
# so create_all materializes them on this test fixture engine.
import agent_os.ai.models  # noqa: F401
import agent_os.db.sqlite_compat  # noqa: F401

# Side-effect imports so create_all sees every table the router walks.
import agent_os.notifications.models  # noqa: F401
import agent_os.sources.models  # noqa: F401
from agent_os.ai import llm_provider
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.db.base import Base, get_db
from agent_os.inbox.prd10_models import (
    InboxItemPriority,
    InboxItemProcessingStatus,
    InboxItemStatus,
    InboxItemType,
    Prd10InboxItem,
)
from agent_os.insights.models import InsightType, Prd10Insight
from agent_os.insights.router import router as insights_router
from agent_os.kb.models import Document, DocumentStatus, DocumentType
from agent_os.knowledge.models import Card


class FakeResearchProvider:
    async def complete(self, messages, tools=None, **kwargs):
        return {
            "content": "## 结论摘要\n基于真实知识资产生成的深度研究报告。\n\n## 下一步建议\n- 完成全链路联调。",
            "role": "assistant",
            "model": "fake-research-llm",
        }


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def sessionmaker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def fixture_user(sessionmaker) -> User:
    async with sessionmaker() as session:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            id=uuid.uuid4(),
            email=f"u{suffix}@example.com",
            username=f"u_{suffix}",
            password_hash="x",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def app(sessionmaker, fixture_user):
    fastapi_app = FastAPI()
    fastapi_app.include_router(insights_router)

    async def _override_db():
        async with sessionmaker() as session:
            yield session

    async def _override_user():
        return fixture_user

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[get_current_user] = _override_user
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_summary_empty_returns_envelope(client):
    resp = await client.get("/api/v1/insights/summary", params={"range": "week"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert {"capture_count", "knowledge_count", "task_count", "completed_task_count"} <= set(
        data["stats"].keys()
    )
    assert data["theme_distribution"] == []
    assert data["insights"] == []
    assert any(a["type"] == "generate_report" for a in data["recommended_actions"])


@pytest.mark.asyncio
async def test_summary_aggregates_themes_and_stats(
    client, sessionmaker, fixture_user
):
    async with sessionmaker() as s:
        # Two cards with overlapping tags so the theme distribution top entry
        # is deterministic.
        s.add(
            Card(
                user_id=fixture_user.id,
                title="C1",
                content="x",
                tags=["产品设计", "Mydow"],
            )
        )
        s.add(
            Card(
                user_id=fixture_user.id,
                title="C2",
                content="x",
                tags=["产品设计", "PRD10"],
            )
        )
        s.add(
            Document(
                user_id=fixture_user.id,
                title="D1",
                document_type=DocumentType.NOTE.value,
                status=DocumentStatus.READY.value,
            )
        )
        s.add(
            Prd10InboxItem(
                user_id=fixture_user.id,
                type=InboxItemType.MANUAL_TASK.value,
                title="待办",
                status=InboxItemStatus.RECEIVED.value,
                processing_status=InboxItemProcessingStatus.QUEUED.value,
                priority=InboxItemPriority.NORMAL.value,
                auto_process=False,
            )
        )
        s.add(
            Prd10InboxItem(
                user_id=fixture_user.id,
                type=InboxItemType.MANUAL_TASK.value,
                title="已完成",
                status=InboxItemStatus.PROCESSED.value,
                processing_status=InboxItemProcessingStatus.COMPLETED.value,
                priority=InboxItemPriority.NORMAL.value,
                auto_process=False,
            )
        )
        await s.commit()

    resp = await client.get("/api/v1/insights/summary")
    data = resp.json()["data"]
    assert data["stats"]["knowledge_count"] == 1
    assert data["stats"]["task_count"] == 2
    assert data["stats"]["completed_task_count"] == 1
    top_theme = data["theme_distribution"][0]
    assert top_theme["name"] == "产品设计"
    assert top_theme["value"] == 2


@pytest.mark.asyncio
async def test_list_insights_filters_by_type_and_status(
    client, sessionmaker, fixture_user
):
    async with sessionmaker() as s:
        s.add(
            Prd10Insight(
                user_id=fixture_user.id,
                insight_type=InsightType.THEME_TREND.value,
                title="主题趋势",
                summary="近期产品类内容增长",
                status="ready",
            )
        )
        s.add(
            Prd10Insight(
                user_id=fixture_user.id,
                insight_type=InsightType.TASK_RISK.value,
                title="任务风险",
                summary="3 个任务超期",
                status="dismissed",
            )
        )
        await s.commit()

    resp = await client.get(
        "/api/v1/insights",
        params={"insight_type": "theme_trend", "status": "ready"},
    )
    items = resp.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "主题趋势"


@pytest.mark.asyncio
async def test_create_and_dismiss_insight(client):
    created = await client.post(
        "/api/v1/insights",
        json={
            "insight_type": "knowledge_gap",
            "title": "建议补充资料",
            "summary": "X 主题缺少近期资料",
        },
    )
    assert created.status_code == 201
    iid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "ready"

    dismissed = await client.post(f"/api/v1/insights/{iid}/dismiss")
    assert dismissed.status_code == 200
    assert dismissed.json()["data"]["status"] == "dismissed"


@pytest.mark.asyncio
async def test_generate_report_persists_insight_and_job(
    client, sessionmaker, fixture_user
):
    resp = await client.post(
        "/api/v1/reports/generate",
        json={"report_type": "daily", "include_sources": True},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()["data"]
    assert body["status"] == "completed"
    report_id = body["report_id"]

    detail = await client.get(f"/api/v1/reports/{report_id}")
    assert detail.status_code == 200
    payload = detail.json()["data"]
    assert payload["insight_type"] == "daily_summary"
    assert "stats" in payload["report"]


@pytest.mark.asyncio
async def test_deep_research_task_uses_llm_and_saves_document(
    client, sessionmaker, fixture_user
):
    async with sessionmaker() as session:
        session.add(
            Card(
                user_id=fixture_user.id,
                title="Mydow 数据链路",
                summary="灵感采集、网页剪藏、RAG 和 Skills 需要全链路联调。",
                content="所有结果必须落库并可追溯。",
                content_type="insight",
                tags=["Mydow", "RAG"],
            )
        )
        session.add(
            Document(
                user_id=fixture_user.id,
                title="网页剪藏验收",
                summary="网页剪藏需要抓取正文并保存为知识库文档。",
                content="剪藏正文、标题、摘要、标签都必须来自真实处理。",
                document_type=DocumentType.MARKDOWN.value,
                status=DocumentStatus.READY.value,
                tags=["网页剪藏"],
            )
        )
        await session.commit()

    llm_provider.set_test_provider(FakeResearchProvider())
    try:
        resp = await client.post(
            "/api/v1/research/tasks",
            json={"topic": "Mydow 数据链路", "scope": "知识库", "output": "研究报告"},
        )
    finally:
        llm_provider.set_test_provider(None)

    assert resp.status_code == 202, resp.text
    data = resp.json()["data"]
    assert data["status"] == "completed"
    assert data["used_llm"] is True
    assert data["model"] == "fake-research-llm"
    assert uuid.UUID(data["report_id"])
    assert uuid.UUID(data["document_id"])

    async with sessionmaker() as session:
        saved = await session.get(Document, uuid.UUID(data["document_id"]))
        assert saved is not None
        assert saved.extra["kind"] == "deep_research"
        assert "深度研究" in saved.tags


@pytest.mark.asyncio
async def test_generate_report_validation_error_on_invalid_range(client):
    resp = await client.post(
        "/api/v1/reports/generate",
        json={
            "report_type": "weekly",
            "time_range": {"start": "2026-12-31T00:00:00+00:00", "end": "2026-01-01T00:00:00+00:00"},
        },
    )
    assert resp.status_code == 400
    body = resp.json()["detail"]
    assert body["code"] == "VALIDATION_ERROR"
