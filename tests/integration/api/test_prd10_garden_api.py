"""PRD10 Garden router tests (Agent 3)."""

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

import agent_os.agent.models  # noqa: F401
import agent_os.ai.models  # noqa: F401
import agent_os.conversations.models  # noqa: F401
import agent_os.db.sqlite_compat  # noqa: F401

# Side-effect imports: register all transitively-referenced PRD10 / PRD4
# tables on ``Base.metadata`` so ``create_all`` can resolve foreign keys.
import agent_os.inbox.prd10_models  # noqa: F401
import agent_os.insights.models  # noqa: F401 — prd10_insights for POST /garden/insights
import agent_os.items.models  # noqa: F401
import agent_os.jobs.models  # noqa: F401
import agent_os.kb.models  # noqa: F401
import agent_os.knowledge.models  # noqa: F401
import agent_os.notifications.models  # noqa: F401
import agent_os.search_engine.models  # noqa: F401
import agent_os.skills.runs  # noqa: F401
import agent_os.sources.models  # noqa: F401
import agent_os.stage3.models  # noqa: F401
import agent_os.tasks.models  # noqa: F401
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.db.base import Base, get_db
from agent_os.garden.models import DailyInsight
from agent_os.garden.router_prd10 import router as garden_router
from agent_os.items.models import Workspace
from agent_os.knowledge.models import Card


@pytest_asyncio.fixture
async def prd10_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
async def fixture_workspace(prd10_session, fixture_user) -> Workspace:
    ws = Workspace(
        id=uuid.uuid4(),
        owner_id=fixture_user.id,
        name="W",
    )
    prd10_session.add(ws)
    await prd10_session.commit()
    await prd10_session.refresh(ws)
    return ws


@pytest_asyncio.fixture
async def app(prd10_engine, fixture_user):
    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )

    fastapi_app = FastAPI()
    fastapi_app.include_router(garden_router)

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


async def _make_card(
    session: AsyncSession,
    *,
    user: User,
    workspace: Workspace,
    title: str,
    tags: list[str] | None = None,
) -> Card:
    card = Card(
        user_id=user.id,
        workspace_id=workspace.id,
        title=title,
        content=title,
        para_type="concept",
        tags=tags or [],
    )
    session.add(card)
    await session.commit()
    await session.refresh(card)
    return card


# ---------------------------------------------------------------------------
# /api/v1/garden/overview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGardenOverview:
    async def test_empty_garden_returns_zeros(self, client):
        resp = await client.get("/api/v1/garden/overview")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["node_count"] == 0
        assert data["edge_count"] == 0
        assert data["strong_edge_count"] == 0
        assert data["top_topics"] == []
        assert data["recent_insights"] == []

    async def test_overview_counts_cards_and_topics(
        self, client, prd10_session, fixture_user, fixture_workspace
    ):
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="A",
            tags=["产品设计", "AI"],
        )
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="B",
            tags=["产品设计", "运营"],
        )
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="C",
            tags=["AI"],
        )

        resp = await client.get("/api/v1/garden/overview")
        data = resp.json()["data"]
        assert data["node_count"] == 3
        # ``产品设计`` and ``AI`` each appear twice; ``运营`` once.
        assert data["top_topics"][:2] == ["产品设计", "AI"] or \
            data["top_topics"][:2] == ["AI", "产品设计"]

    async def test_overview_includes_recent_insights(
        self, client, prd10_session, fixture_user, fixture_workspace
    ):
        insight = DailyInsight(
            id=uuid.uuid4(),
            workspace_id=fixture_workspace.id,
            user_id=fixture_user.id,
            title="本周热点",
            content="...",
            status="stable",
            level=2,
            canonical_hash=uuid.uuid4().hex,
            stability_score=0.9,
            evidence_count=4,
            source_item_ids="[]",
        )
        prd10_session.add(insight)
        await prd10_session.commit()

        resp = await client.get("/api/v1/garden/overview")
        data = resp.json()["data"]
        assert len(data["recent_insights"]) == 1
        item = data["recent_insights"][0]
        assert item["title"] == "本周热点"
        assert item["status"] == "stable"
        assert item["level"] == 2


# ---------------------------------------------------------------------------
# /api/v1/garden/graph
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGardenGraph:
    async def test_empty_graph_success(self, client):
        resp = await client.get("/api/v1/garden/graph")
        body = resp.json()
        assert resp.status_code == 200
        assert body["data"]["nodes"] == []
        assert body["data"]["edges"] == []

    async def test_graph_returns_user_cards_as_nodes(
        self, client, prd10_session, fixture_user, fixture_workspace
    ):
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="第一张卡",
            tags=["产品设计"],
        )
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="第二张卡",
            tags=["AI"],
        )
        resp = await client.get("/api/v1/garden/graph")
        data = resp.json()["data"]
        labels = sorted(n["label"] for n in data["nodes"])
        assert labels == ["第一张卡", "第二张卡"]
        for n in data["nodes"]:
            assert n["object_type"] == "card"
            assert n["type"] == "card"

    async def test_graph_topic_filter(
        self, client, prd10_session, fixture_user, fixture_workspace
    ):
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="UI",
            tags=["产品设计"],
        )
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="Backend",
            tags=["Backend"],
        )
        resp = await client.get(
            "/api/v1/garden/graph", params={"topic": "产品设计"}
        )
        data = resp.json()["data"]
        labels = [n["label"] for n in data["nodes"]]
        assert labels == ["UI"]

    async def test_graph_invalid_range(self, client):
        resp = await client.get(
            "/api/v1/garden/graph", params={"range": "weird"}
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# §6.4 — derived semantic edges (Jaccard over Card.tags)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGardenDerivedEdges:
    """PRD10 §18 + todo §6.4: derive `semantic_related` / `support` edges
    from `Card.tags` overlap so the biz Garden page is not visually empty
    when no `KnowledgeCardLink` rows exist (the legacy table requires
    `items.id` FKs that PRD10 capture/feed never populate).
    """

    async def test_overview_counts_derived_edges(
        self, client, prd10_session, fixture_user, fixture_workspace
    ):
        # 3 cards, share enough tags to produce Jaccard >= 0.2 between
        # at least the AI/产品 pair.
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="A",
            tags=["产品设计", "AI", "Mydow"],
        )
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="B",
            tags=["产品设计", "AI"],
        )
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="C",
            tags=["AI", "运营"],
        )

        resp = await client.get("/api/v1/garden/overview")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["node_count"] == 3
        # Overview now exposes derived counts; total edge_count must be
        # at least the derived count (legacy can add on top).
        assert data["derived_edge_count"] >= 2
        assert data["edge_count"] >= data["derived_edge_count"]
        # A↔B share 2/3 tags (Jaccard 2/3 ≈ 0.667), strong threshold is
        # 0.7, so it's *not* strong; A↔C share 1/4 (0.25), B↔C share
        # 1/3 (0.333) — none reach 0.7 unless we change tags. Verify
        # strong logic by adding a near-duplicate pair.
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="D",
            tags=["产品设计", "AI", "Mydow"],
        )
        resp2 = await client.get("/api/v1/garden/overview")
        data2 = resp2.json()["data"]
        # A and D share all 3 tags → weight 1.0 → strong edge.
        assert data2["derived_edge_count"] >= 3
        assert data2["strong_edge_count"] >= 1

    async def test_graph_derived_edges_have_jaccard_weight(
        self, client, prd10_session, fixture_user, fixture_workspace
    ):
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="UI 笔记",
            tags=["UI", "产品"],
        )
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="UX 笔记",
            tags=["UI", "产品", "用户研究"],
        )
        resp = await client.get("/api/v1/garden/graph")
        data = resp.json()["data"]
        assert len(data["nodes"]) == 2
        assert len(data["edges"]) >= 1
        edge = data["edges"][0]
        assert edge["relation_type"] in {"semantic_related", "support"}
        # 2/3 overlap → 0.6667
        assert 0.66 < edge["weight"] < 0.67
        assert "shared_tags" in edge
        assert set(edge["shared_tags"]) >= {"UI", "产品"}

    async def test_graph_same_folder_uses_support_relation(
        self, client, prd10_session, fixture_user, fixture_workspace
    ):
        # Two cards in the same folder with overlapping tags should be
        # tagged as ``support`` rather than ``semantic_related``.
        from agent_os.kb.models import Folder

        folder = Folder(
            user_id=fixture_user.id,
            name="设计",
            description="同 folder edge",
        )
        prd10_session.add(folder)
        await prd10_session.commit()
        await prd10_session.refresh(folder)

        c1 = Card(
            user_id=fixture_user.id,
            workspace_id=fixture_workspace.id,
            title="同folder-1",
            content="x",
            para_type="concept",
            tags=["AI", "产品"],
            folder_id=folder.id,
        )
        c2 = Card(
            user_id=fixture_user.id,
            workspace_id=fixture_workspace.id,
            title="同folder-2",
            content="x",
            para_type="concept",
            tags=["AI", "产品"],
            folder_id=folder.id,
        )
        prd10_session.add(c1)
        prd10_session.add(c2)
        await prd10_session.commit()

        resp = await client.get("/api/v1/garden/graph")
        data = resp.json()["data"]
        edges = [e for e in data["edges"] if "support" == e["relation_type"]]
        assert len(edges) >= 1
        # Cross-folder fallback: edges that aren't between same folder
        # cards must still be semantic_related.
        for edge in data["edges"]:
            assert edge["relation_type"] in {"semantic_related", "support"}

    async def test_graph_node_size_reflects_degree(
        self, client, prd10_session, fixture_user, fixture_workspace
    ):
        # 3 cards all sharing one tag → triangle; each node has degree 2
        # → node.size == 3 (1 + degree).
        for name in ("A", "B", "C"):
            await _make_card(
                prd10_session,
                user=fixture_user,
                workspace=fixture_workspace,
                title=name,
                tags=["共享"],
            )
        resp = await client.get("/api/v1/garden/graph")
        data = resp.json()["data"]
        assert len(data["nodes"]) == 3
        sizes = sorted(n["size"] for n in data["nodes"])
        # Triangle → each node has degree 2 → size 3.
        assert sizes == [3, 3, 3]

    async def test_graph_no_edges_when_no_tag_overlap(
        self, client, prd10_session, fixture_user, fixture_workspace
    ):
        # Cards with completely disjoint tags must not be connected.
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="A",
            tags=["产品"],
        )
        await _make_card(
            prd10_session,
            user=fixture_user,
            workspace=fixture_workspace,
            title="B",
            tags=["运营"],
        )
        resp = await client.get("/api/v1/garden/graph")
        data = resp.json()["data"]
        assert len(data["nodes"]) == 2
        assert data["edges"] == []
        # Isolated nodes still report size==1 (1 + 0 degree).
        for n in data["nodes"]:
            assert n["size"] == 1


# ---------------------------------------------------------------------------
# §16.12 — POST /api/v1/garden/insights (v1.4 custom insight modal)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGardenInsightCreate:
    async def test_create_custom_insight_with_connected_notes(self, client):
        resp = await client.post(
            "/api/v1/garden/insights",
            json={
                "topic": "  测试自定义洞察  ",
                "connected_note_ids": ["note_a", "note_b"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["title"] == "测试自定义洞察"
        assert data["insight_type"] == "connection"
        assert data["extra"]["connected_note_ids"] == ["note_a", "note_b"]
        assert data["extra"]["source"] == "garden_custom"
        out_ids = data.get("connected_note_ids") or data.get("connectedNoteIds")
        assert out_ids == ["note_a", "note_b"]
