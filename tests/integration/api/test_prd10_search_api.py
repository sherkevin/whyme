"""PRD10 Global Search router tests (Agent 3 ownership).

Covers ``GET /api/v1/search`` and ``GET /api/v1/search/suggestions`` from
``agent_os.search_engine.router_prd10``.

The fixtures build a tiny FastAPI app that mounts only the PRD10 search
router and overrides ``get_db`` / ``get_current_user`` so we don't pull in
the full application surface (which would force PRD4/auth setup we don't
need here).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import agent_os.db.sqlite_compat  # noqa: F401  (registers PG UUID -> CHAR(32))
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.db.base import get_db
from agent_os.search_engine.models import SearchIndex
from agent_os.search_engine.router_prd10 import router as prd10_search_router

PRD10_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def prd10_engine():
    engine = create_async_engine(
        PRD10_DB_URL,
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    async with engine.begin() as conn:
        def _create(connection):
            User.__table__.create(connection, checkfirst=True)
            SearchIndex.__table__.create(connection, checkfirst=True)

        await conn.run_sync(_create)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def prd10_session(prd10_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def fixture_user(prd10_session) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        email=f"u{suffix}@example.com",
        username=f"u_{suffix}",
        password_hash="x",
        is_active=True,
    )
    prd10_session.add(user)
    await prd10_session.commit()
    await prd10_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def app(prd10_engine, fixture_user):
    """Minimal FastAPI app with only the PRD10 search router mounted."""

    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )

    fastapi_app = FastAPI()
    fastapi_app.include_router(prd10_search_router)

    async def _override_db():
        async with factory() as session:
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed(
    session: AsyncSession,
    *,
    user: User,
    object_type: str,
    title: str,
    summary: str | None = None,
    content: str | None = None,
    user_owned: bool = True,
    embedding: list[float] | None = None,
    embedding_id: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> SearchIndex:
    row = SearchIndex(
        item_type=object_type,
        item_id=uuid.uuid4(),
        user_id=(user.id if user_owned else None),
        title=title,
        summary=summary,
        content=content,
        tags=[object_type],
        embedding=embedding,
        embedding_id=embedding_id,
    )
    if created_at is not None:
        row.created_at = created_at
    if updated_at is not None:
        row.updated_at = updated_at
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGlobalSearch:
    async def test_empty_index_returns_success_envelope(self, client):
        resp = await client.get("/api/v1/search", params={"q": "anything"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["items"] == []
        assert body["data"]["pagination"]["total"] == 0
        assert body["data"]["pagination"]["has_more"] is False
        assert body["request_id"].startswith("req_")

    async def test_match_by_title_and_summary(
        self, client, prd10_session, fixture_user
    ):
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="UI 设计规范",
            summary="Mydow V1 UI 设计文档",
            content="首页包含 输入区 和内容流",
        )
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="card",
            title="后端 API 设计",
            summary="REST 接口约定",
        )

        resp = await client.get("/api/v1/search", params={"q": "UI"})
        body = resp.json()
        assert resp.status_code == 200
        assert body["success"] is True
        items = body["data"]["items"]
        assert len(items) == 1
        assert items[0]["object_type"] == "document"
        assert items[0]["title"] == "UI 设计规范"
        assert "<mark>UI</mark>" in items[0]["highlight"]
        assert items[0]["url"].startswith("/kb/")

    async def test_object_type_filter(
        self, client, prd10_session, fixture_user
    ):
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="文档 alpha",
        )
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="card",
            title="卡片 alpha",
        )

        resp = await client.get(
            "/api/v1/search",
            params=[("q", "alpha"), ("object_type", "document")],
        )
        body = resp.json()
        assert resp.status_code == 200
        items = body["data"]["items"]
        assert len(items) == 1
        assert items[0]["object_type"] == "document"

    async def test_user_isolation_does_not_leak(
        self, client, prd10_session, fixture_user
    ):
        # Row owned by another user.
        other = User(
            id=uuid.uuid4(),
            email=f"other_{uuid.uuid4().hex[:6]}@example.com",
            username=f"other_{uuid.uuid4().hex[:6]}",
            password_hash="x",
            is_active=True,
        )
        prd10_session.add(other)
        await prd10_session.commit()

        prd10_session.add(
            SearchIndex(
                item_type="card",
                item_id=uuid.uuid4(),
                user_id=other.id,
                title="对方的卡片 secret",
            )
        )
        # Legacy un-owned row should still be visible (PRD10 ingestion path).
        prd10_session.add(
            SearchIndex(
                item_type="card",
                item_id=uuid.uuid4(),
                user_id=None,
                title="legacy card secret",
            )
        )
        await prd10_session.commit()

        resp = await client.get("/api/v1/search", params={"q": "secret"})
        body = resp.json()
        items = body["data"]["items"]
        titles = sorted(i["title"] for i in items)
        assert titles == ["legacy card secret"]

    async def test_pagination_metadata(
        self, client, prd10_session, fixture_user
    ):
        for i in range(5):
            await _seed(
                prd10_session,
                user=fixture_user,
                object_type="card",
                title=f"卡片-{i}",
                summary=f"summary {i} foo",
            )

        resp = await client.get(
            "/api/v1/search",
            params={"q": "foo", "page": 1, "page_size": 2},
        )
        body = resp.json()
        pagination = body["data"]["pagination"]
        assert pagination["page"] == 1
        assert pagination["page_size"] == 2
        assert pagination["total"] == 5
        assert pagination["has_more"] is True
        assert len(body["data"]["items"]) == 2

    async def test_title_only_skips_summary_match(
        self, client, prd10_session, fixture_user
    ):
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="仅标题不含",
            summary="unique_blob_alpha summary hit",
        )
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="card",
            title="unique_blob_alpha in title",
            summary="nothing",
        )

        r0 = await client.get(
            "/api/v1/search",
            params={"q": "unique_blob_alpha", "title_only": True},
        )
        items0 = r0.json()["data"]["items"]
        assert len(items0) == 1
        assert items0[0]["title"] == "unique_blob_alpha in title"

        r1 = await client.get(
            "/api/v1/search",
            params={"q": "unique_blob_alpha", "title_only": False},
        )
        titles = {i["title"] for i in r1.json()["data"]["items"]}
        assert titles == {
            "仅标题不含",
            "unique_blob_alpha in title",
        }

    async def test_mine_only_excludes_legacy_null_user_rows(
        self, client, prd10_session, fixture_user
    ):
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="card",
            title="owned zqmine",
            summary="x",
            user_owned=True,
        )
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="card",
            title="legacy zqmine",
            summary="x",
            user_owned=False,
        )

        r_open = await client.get("/api/v1/search", params={"q": "zqmine"})
        assert len(r_open.json()["data"]["items"]) == 2

        r_mine = await client.get(
            "/api/v1/search",
            params={"q": "zqmine", "mine_only": True},
        )
        items = r_mine.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["title"] == "owned zqmine"

    async def test_date_preset_filters_old_rows(
        self, client, prd10_session, fixture_user
    ):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=40)
        recent = now - timedelta(days=5)
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="stale zqdate",
            created_at=old,
            updated_at=old,
        )
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="fresh zqdate",
            created_at=recent,
        )

        r = await client.get(
            "/api/v1/search",
            params={"q": "zqdate", "date_preset": "30d"},
        )
        titles = {i["title"] for i in r.json()["data"]["items"]}
        assert titles == {"fresh zqdate"}

    async def test_sort_relevance_forces_hybrid_metadata(
        self, client, prd10_session, fixture_user
    ):
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="card",
            title="rq hybrid card",
            summary="rq token",
        )
        resp = await client.get(
            "/api/v1/search",
            params={"q": "rq", "sort": "relevance"},
        )
        data = resp.json()["data"]
        assert data["mode"] == "hybrid"
        assert data["sort"] == "relevance"


@pytest.mark.asyncio
class TestSearchModes:
    async def test_keyword_mode_default_envelope_includes_mode(
        self, client, prd10_session, fixture_user
    ):
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="card",
            title="Mode 检查 alpha",
            summary="alpha keyword 默认",
        )
        resp = await client.get("/api/v1/search", params={"q": "alpha"})
        body = resp.json()["data"]
        assert body["mode"] == "keyword"
        assert body["items"][0]["score"] == 0.0  # keyword path skips ranking.

    async def test_semantic_mode_ranks_by_relevance(
        self, client, prd10_session, fixture_user
    ):
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="无关文档",
            summary="完全不同主题",
            content="日常杂记，不涉及搜索",
        )
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="搜索引擎入门",
            summary="语义搜索基础",
            content="语义搜索 与 嵌入向量 的基础知识 搜索",
        )
        resp = await client.get(
            "/api/v1/search", params={"q": "语义搜索", "mode": "semantic"}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["mode"] == "semantic"
        assert data["items"], "semantic mode should rank at least one row"
        top = data["items"][0]
        assert top["title"] == "搜索引擎入门"
        assert top["score"] > 0

    async def test_semantic_mode_uses_persisted_embeddings(
        self, client, prd10_session, fixture_user
    ):
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="标题不含查询词 A",
            summary="正文也不含查询词",
            content="完全无关",
            embedding=[1.0] + [0.0] * 63,
            embedding_id="test:near",
        )
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="语义搜索 表面命中",
            summary="语义搜索 词法命中",
            content="语义搜索",
            embedding=[0.0, 1.0] + [0.0] * 62,
            embedding_id="test:far",
        )
        # The query embedding is generated locally, so make the first row's
        # vector exactly match it after seeding.
        from agent_os.search_engine.embeddings import embed_text

        near = (
            await prd10_session.execute(
                select(SearchIndex).where(SearchIndex.embedding_id == "test:near")
            )
        ).scalar_one()
        near.embedding = embed_text("语义搜索")
        await prd10_session.commit()

        resp = await client.get(
            "/api/v1/search", params={"q": "语义搜索", "mode": "semantic"}
        )
        data = resp.json()["data"]
        assert data["items"][0]["title"] == "标题不含查询词 A"
        assert data["items"][0]["score"] > 0.99

    async def test_hybrid_mode_combines_filter_and_ranking(
        self, client, prd10_session, fixture_user
    ):
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="card",
            title="高频命中卡片",
            summary="搜索 hybrid 命中 多次 搜索",
            content="hybrid 搜索 hybrid",
        )
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="card",
            title="只命中一次",
            summary="hybrid",
        )
        resp = await client.get(
            "/api/v1/search", params={"q": "hybrid", "mode": "hybrid"}
        )
        data = resp.json()["data"]
        assert data["mode"] == "hybrid"
        assert data["items"][0]["title"] == "高频命中卡片"
        assert data["items"][0]["score"] >= data["items"][-1]["score"]


@pytest.mark.asyncio
class TestSearchSuggestions:
    async def test_blank_query_returns_empty_list(self, client):
        resp = await client.get("/api/v1/search/suggestions", params={"q": "  "})
        body = resp.json()
        assert resp.status_code == 200
        assert body["success"] is True
        assert body["data"]["suggestions"] == []

    async def test_prefix_match(self, client, prd10_session, fixture_user):
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="UI 设计规范",
        )
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="document",
            title="UX 研究方法",
        )
        await _seed(
            prd10_session,
            user=fixture_user,
            object_type="card",
            title="API 网关计划",
        )

        resp = await client.get(
            "/api/v1/search/suggestions", params={"q": "U"}
        )
        body = resp.json()
        suggestions = body["data"]["suggestions"]
        titles = sorted(s["title"] for s in suggestions)
        assert titles == ["UI 设计规范", "UX 研究方法"]
        for item in suggestions:
            assert item["object_type"] in ("document", "card")
            assert item["object_id"]
