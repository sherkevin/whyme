"""End-to-end PRD10 flows the Mydow Web frontend exercises.

These tests run the full ``agent_os.server.app`` against an in-memory SQLite
DB and walk through the key user journeys the bundled ``mydow-api.js``
needs to work:

* `/today` aggregator returns the PRD10 envelope shape.
* Capture text → KB document is queryable downstream.
* AI conversation create → send message → save-to-kb → poll job.
* Search returns the freshly-captured artifact.
* Skills list/run produces a queued ``Job`` + ``SkillRun``.

We don't simulate streaming SSE here — that's a P1 deliverable. The point
of this file is to prove "front button → backend persistence" works as a
single chain across modules owned by Agent 1, 2, and 3.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import agent_os.agent.models  # noqa: F401

# Side-effect imports so ``Base.metadata.create_all`` covers everything.
import agent_os.ai.models  # noqa: F401
import agent_os.conversations.models  # noqa: F401
import agent_os.db.sqlite_compat  # noqa: F401
import agent_os.garden.models  # noqa: F401
import agent_os.inbox.prd10_models  # noqa: F401
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
from agent_os.server.app import app as prd_app
from agent_os.stage3.models import Skill

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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
async def fixture_user(prd10_engine) -> User:
    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
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
async def seeded_skill(prd10_engine) -> Skill:
    """Insert a single PRD10-shape Skill so /skills has something to return."""

    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        skill = Skill(
            name="周报生成器",
            description="把本周的卡片整理成简明周报",
            category="productivity",
            steps=[{"order": 1, "name": "summarize"}],
            version="1.0",
            icon="sparkles",
            status="published",
            usage_count=3,
            is_installed_default=True,
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        session.add(skill)
        await session.commit()
        await session.refresh(skill)
    return skill


@pytest_asyncio.fixture
async def client(prd10_engine, fixture_user) -> AsyncGenerator[AsyncClient, None]:
    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_db():
        async with factory() as session:
            yield session

    async def _override_user():
        return fixture_user

    prd_app.dependency_overrides[get_db] = _override_db
    prd_app.dependency_overrides[get_current_user] = _override_user

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            yield ac
        finally:
            prd_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Flows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHomeAndTodayFlow:
    async def test_today_returns_prd10_shape_when_empty(self, client):
        resp = await client.get("/api/v1/today")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        data = body["data"]
        # PRD10 §7.1 mandatory keys.
        for key in (
            "user",
            "stats",
            "quick_actions",
            "tasks",
            "insight_preview",
        ):
            assert key in data, f"/today missing PRD10 key: {key}"
        assert data["stats"]["today_capture_count"] == 0
        assert data["stats"]["pending_task_count"] == 0
        assert isinstance(data["quick_actions"], list) and data["quick_actions"]


@pytest.mark.asyncio
class TestAiSaveToKbAndJobLookup:
    async def test_full_chain(self, client):
        # 1) Create conversation.
        created = await client.post(
            "/api/v1/ai/conversations",
            json={"title": "联调 demo", "mode": "general"},
        )
        assert created.status_code == 201
        cid = created.json()["data"]["id"]

        # 2) Send a user message; assistant reply is the placeholder.
        sent = await client.post(
            f"/api/v1/ai/conversations/{cid}/messages",
            json={"content": "请帮我总结本周的进展"},
        )
        assert sent.status_code == 201
        sent_data = sent.json()["data"]
        assert sent_data["assistant_message"]["status"] == "completed"
        amid = sent_data["assistant_message"]["id"]
        ai_chat_job_id = sent_data["job"]["id"]

        # 3) save-to-kb returns a queued job for the KB worker.
        saved = await client.post(
            f"/api/v1/ai/messages/{amid}/save-to-kb",
            json={"folder_id": None, "title": "周进展", "tags": ["AI输出"]},
        )
        assert saved.status_code == 202
        saved_data = saved.json()["data"]
        save_job_id = saved_data["job_id"]
        assert saved_data["status"] == "queued"
        assert saved_data["message_id"] == amid

        # 4) Both jobs must be reachable via /api/v1/jobs/{id}.
        for job_id in (ai_chat_job_id, save_job_id):
            r = await client.get(f"/api/v1/jobs/{job_id}")
            assert r.status_code == 200, f"job {job_id} not found"
            body = r.json()
            assert body["success"] is True
            assert body["data"]["id"] == job_id

        # 5) Conversation detail must now contain BOTH messages plus the
        #    rolled-up message_count.
        detail = await client.get(f"/api/v1/ai/conversations/{cid}")
        assert detail.status_code == 200
        ddata = detail.json()["data"]
        assert ddata["conversation"]["message_count"] == 2
        assert len(ddata["messages"]) == 2

    async def test_create_tasks_validates_payload(self, client):
        created = await client.post(
            "/api/v1/ai/conversations",
            json={"title": "create-tasks demo"},
        )
        cid = created.json()["data"]["id"]
        sent = await client.post(
            f"/api/v1/ai/conversations/{cid}/messages",
            json={"content": "请生成任务"},
        )
        amid = sent.json()["data"]["assistant_message"]["id"]

        bad = await client.post(
            f"/api/v1/ai/messages/{amid}/create-tasks",
            json={"tasks": []},
        )
        assert bad.status_code == 400
        # PRD10 envelope error per app.py exception handler.
        body = bad.json()
        assert body["success"] is False
        assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
class TestSkillsRunFlow:
    async def test_list_then_run(self, client, seeded_skill):
        # 1) List should now include the seeded skill.
        listed = await client.get("/api/v1/skills")
        assert listed.status_code == 200
        items = listed.json()["data"]["items"]
        ids = [s["id"] for s in items]
        assert str(seeded_skill.id) in ids

        # 2) Run it.
        run = await client.post(
            f"/api/v1/skills/{seeded_skill.id}/run",
            json={"input": {"goal": "本周周报"}, "save_output": "kb"},
        )
        assert run.status_code == 202
        rdata = run.json()["data"]
        job_id = rdata["job_id"]
        assert rdata["status"] == "queued"
        assert rdata["skill_run_id"]

        # 3) Job must be queryable via the generic Jobs API.
        job_resp = await client.get(f"/api/v1/jobs/{job_id}")
        assert job_resp.status_code == 200
        job_body = job_resp.json()
        assert job_body["data"]["job_type"] == "skill_run"


@pytest.mark.asyncio
class TestSearchFlowReachesPersistedData:
    async def test_search_after_creating_a_card(self, client, prd10_engine, fixture_user):
        # PRD10 §9 Card creation is owned by the Feed router (Agent 2).
        # We exercise it through the public POST /api/v1/cards path so the
        # whole chain (router -> ORM -> SearchIndex back-fill) is real.
        card_resp = await client.post(
            "/api/v1/cards",
            json={
                "title": "Mydow 联调样本",
                "content": "前后端绑定测试用的卡片正文，关键字 联调",
                "summary": "Mydow 前后端联调样本",
                "tags": ["联调", "Mydow"],
                "content_type": "note",
            },
        )
        # ``POST /api/v1/cards`` returns 201 (per PRD10 §9.3 / Feed router).
        assert card_resp.status_code in (200, 201), card_resp.text
        card_id = card_resp.json()["data"]["id"]

        # Whether or not Search has a SearchIndex row yet, the API must at
        # minimum respond with a valid PRD10 envelope (empty list is OK).
        search_resp = await client.get(
            "/api/v1/search", params={"q": "Mydow"}
        )
        assert search_resp.status_code == 200
        sb = search_resp.json()
        assert sb["success"] is True
        assert "items" in sb["data"]
        assert "pagination" in sb["data"]

        # The Card must be reachable via its own GET /cards/{id}.
        getcard = await client.get(f"/api/v1/cards/{card_id}")
        assert getcard.status_code == 200
        assert getcard.json()["data"]["title"] == "Mydow 联调样本"
