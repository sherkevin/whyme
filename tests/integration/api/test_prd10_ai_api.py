"""PRD10 Mydow AI conversations router tests (Agent 3)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

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

import agent_os.db.sqlite_compat  # noqa: F401
from agent_os.ai.models import AIConversation, AIMessage
from agent_os.ai.router import router as ai_router
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.db.base import get_db
from agent_os.jobs.models import Job
from agent_os.search_engine.models import SearchIndex


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
        def _create(connection):
            User.__table__.create(connection, checkfirst=True)
            Job.__table__.create(connection, checkfirst=True)
            SearchIndex.__table__.create(connection, checkfirst=True)
            AIConversation.__table__.create(connection, checkfirst=True)
            AIMessage.__table__.create(connection, checkfirst=True)

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
    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )

    fastapi_app = FastAPI()
    fastapi_app.include_router(ai_router)

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
# /api/v1/ai/conversations  (list + create + detail)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConversationsCRUD:
    async def test_list_empty_returns_paginated_envelope(self, client):
        resp = await client.get("/api/v1/ai/conversations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["items"] == []
        assert body["data"]["pagination"]["total"] == 0
        assert body["request_id"].startswith("req_")

    async def test_create_conversation_with_defaults(self, client):
        resp = await client.post("/api/v1/ai/conversations", json={})
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["title"] == "新的对话"
        assert data["mode"] == "general"
        assert data["message_count"] == 0

    async def test_create_conversation_validates_mode(self, client):
        resp = await client.post(
            "/api/v1/ai/conversations",
            json={"mode": "bogus"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"

    async def test_create_then_list_with_keyword(self, client):
        await client.post(
            "/api/v1/ai/conversations",
            json={"title": "周报草稿", "mode": "planning"},
        )
        await client.post(
            "/api/v1/ai/conversations",
            json={"title": "产品讨论", "mode": "general"},
        )

        # No keyword → both
        resp = await client.get("/api/v1/ai/conversations")
        assert resp.json()["data"]["pagination"]["total"] == 2

        # Keyword filter
        resp = await client.get(
            "/api/v1/ai/conversations", params={"keyword": "周报"}
        )
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["title"] == "周报草稿"
        assert items[0]["mode"] == "planning"

    async def test_get_detail_404_for_unknown_id(self, client):
        resp = await client.get(
            f"/api/v1/ai/conversations/{uuid.uuid4()}"
        )
        assert resp.status_code == 404
        assert resp.json()["detail"]["code"] == "NOT_FOUND"

    async def test_get_detail_includes_empty_messages(self, client):
        created = await client.post(
            "/api/v1/ai/conversations", json={"title": "T"}
        )
        cid = created.json()["data"]["id"]
        resp = await client.get(f"/api/v1/ai/conversations/{cid}")
        body = resp.json()
        assert resp.status_code == 200
        assert body["data"]["conversation"]["id"] == cid
        assert body["data"]["messages"] == []
        assert body["data"]["related_context"] == []
        assert body["data"]["suggested_followups"] == []

    async def test_get_detail_resolves_context_scope_documents(
        self,
        client,
        prd10_session,
        fixture_user,
    ):
        document_id = uuid.uuid4()
        prd10_session.add(
            SearchIndex(
                user_id=fixture_user.id,
                item_type="document",
                item_id=document_id,
                title="UI 设计规范",
                summary="关于信息架构和按钮状态的设计规范",
                content="正文",
            )
        )
        await prd10_session.commit()

        created = await client.post(
            "/api/v1/ai/conversations",
            json={
                "title": "T",
                "context_scope": {
                    "document_ids": [str(document_id)],
                    "include_recent": False,
                },
            },
        )
        cid = created.json()["data"]["id"]
        resp = await client.get(f"/api/v1/ai/conversations/{cid}")
        body = resp.json()
        assert resp.status_code == 200
        assert body["data"]["conversation"]["context_scope"]["document_ids"] == [
            str(document_id)
        ]
        assert body["data"]["related_context"][0]["object_type"] == "document"
        assert body["data"]["related_context"][0]["object_id"] == str(document_id)


# ---------------------------------------------------------------------------
# /messages  (synchronous reply; no production placeholder)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPostMessage:
    async def _create_conv(self, client) -> str:
        r = await client.post("/api/v1/ai/conversations", json={"title": "S"})
        return r.json()["data"]["id"]

    async def test_send_message_persists_user_and_assistant(self, client):
        cid = await self._create_conv(client)
        resp = await client.post(
            f"/api/v1/ai/conversations/{cid}/messages",
            json={"content": "你好"},
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["user_message"]["role"] == "user"
        assert data["user_message"]["content"] == "你好"
        assert data["assistant_message"]["role"] == "assistant"
        assert data["assistant_message"]["status"] in {"completed", "failed"}
        if data["assistant_message"]["status"] == "failed":
            assert data["assistant_message"]["model"] == "unavailable"
            assert data["assistant_message"]["error"]["code"] == "AI_PROVIDER_DISABLED"
        assert data["assistant_message"]["citations"] == []
        assert data["assistant_message"]["tool_calls"] == []
        assert data["job"]["job_type"] == "ai_chat"
        assert data["job"]["status"] == data["assistant_message"]["status"]
        assert data["conversation"]["message_count"] == 2
        assert data["conversation"]["last_message_preview"]

    async def test_send_message_returns_context_and_citations(
        self,
        client,
        prd10_session,
        fixture_user,
    ):
        document_id = uuid.uuid4()
        prd10_session.add(
            SearchIndex(
                user_id=fixture_user.id,
                item_type="document",
                item_id=document_id,
                title="产品研究摘要",
                summary="产品设计包含用户访谈与信息架构",
                content="产品设计上下文",
            )
        )
        await prd10_session.commit()

        cid = await self._create_conv(client)
        resp = await client.post(
            f"/api/v1/ai/conversations/{cid}/messages",
            json={
                "content": "产品设计",
                "context_scope": {
                    "document_ids": [str(document_id)],
                    "include_recent": False,
                },
            },
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["related_context"][0]["object_id"] == str(document_id)
        citations = data["assistant_message"]["citations"]
        assert citations[0]["object_type"] == "document"
        assert citations[0]["title"] == "产品研究摘要"

    async def test_send_message_validates_uuid(self, client):
        resp = await client.post(
            "/api/v1/ai/conversations/not-a-uuid/messages",
            json={"content": "hi"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"

    async def test_send_message_404_when_conversation_missing(self, client):
        resp = await client.post(
            f"/api/v1/ai/conversations/{uuid.uuid4()}/messages",
            json={"content": "hi"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# save-to-kb / create-tasks  (Job-only MVP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestSaveAssistantOutput:
    async def _create_conv_and_send(self, client) -> dict:
        r = await client.post(
            "/api/v1/ai/conversations", json={"title": "T"}
        )
        cid = r.json()["data"]["id"]
        sent = await client.post(
            f"/api/v1/ai/conversations/{cid}/messages",
            json={"content": "请总结"},
        )
        return sent.json()["data"]

    async def test_save_to_kb_queues_a_job(self, client):
        sent = await self._create_conv_and_send(client)
        amid = sent["assistant_message"]["id"]
        resp = await client.post(
            f"/api/v1/ai/messages/{amid}/save-to-kb",
            json={
                "folder_id": "folder_001",
                "title": "AI 生成的产品分析",
                "tags": ["AI输出"],
            },
        )
        assert resp.status_code == 202
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["status"] == "queued"
        assert body["data"]["job_id"]
        assert body["data"]["message_id"] == amid

    async def test_save_to_kb_rejects_user_messages(self, client):
        sent = await self._create_conv_and_send(client)
        umid = sent["user_message"]["id"]
        resp = await client.post(
            f"/api/v1/ai/messages/{umid}/save-to-kb",
            json={"title": "x"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"

    async def test_create_tasks_requires_non_empty_list(self, client):
        sent = await self._create_conv_and_send(client)
        amid = sent["assistant_message"]["id"]
        resp = await client.post(
            f"/api/v1/ai/messages/{amid}/create-tasks",
            json={"tasks": []},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"

    async def test_create_tasks_queues_a_job(self, client):
        sent = await self._create_conv_and_send(client)
        amid = sent["assistant_message"]["id"]
        resp = await client.post(
            f"/api/v1/ai/messages/{amid}/create-tasks",
            json={
                "tasks": [
                    {
                        "title": "补充知识库接口",
                        "due_at": "2026-05-06T18:00:00+08:00",
                        "priority": "high",
                    }
                ]
            },
        )
        assert resp.status_code == 202
        data = resp.json()["data"]
        assert data["status"] == "queued"
        assert data["task_count"] == 1
        assert data["message_id"] == amid

    async def test_save_to_kb_404_for_unknown_message(self, client):
        resp = await client.post(
            f"/api/v1/ai/messages/{uuid.uuid4()}/save-to-kb",
            json={"title": "x"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cancel / regenerate (PRD10 §11.5 / §11.6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCancelMessage:
    async def _create_conv_and_send(self, client) -> dict:
        r = await client.post("/api/v1/ai/conversations", json={"title": "C"})
        cid = r.json()["data"]["id"]
        sent = await client.post(
            f"/api/v1/ai/conversations/{cid}/messages",
            json={"content": "请生成"},
        )
        return sent.json()["data"]

    async def test_cancel_pending_message(self, client, prd10_session):
        sent = await self._create_conv_and_send(client)
        amid = sent["assistant_message"]["id"]

        # Force the assistant message back into a cancellable state so we
        # can exercise the real transition regardless of the current LLM mode.
        from agent_os.ai.models import AIMessage, AIMessageStatus

        result = await prd10_session.execute(
            select(AIMessage).where(AIMessage.id == uuid.UUID(amid))
        )
        msg = result.scalar_one()
        msg.status = AIMessageStatus.PENDING.value
        await prd10_session.commit()

        resp = await client.post(f"/api/v1/ai/messages/{amid}/cancel")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["cancelled"] is True
        assert body["data"]["message"]["status"] == "canceled"

    async def test_cancel_failed_message_is_idempotent(self, client):
        sent = await self._create_conv_and_send(client)
        amid = sent["assistant_message"]["id"]

        resp = await client.post(f"/api/v1/ai/messages/{amid}/cancel")
        assert resp.status_code == 200
        body = resp.json()["data"]
        # Completed or failed replies are already terminal; cancel must not
        # rewrite history but must still return a clean envelope.
        assert body["cancelled"] is False
        assert body["message"]["status"] == sent["assistant_message"]["status"]

    async def test_cancel_404_for_unknown_message(self, client):
        resp = await client.post(
            f"/api/v1/ai/messages/{uuid.uuid4()}/cancel"
        )
        assert resp.status_code == 404

    async def test_cancel_rejects_user_message(self, client):
        sent = await self._create_conv_and_send(client)
        umid = sent["user_message"]["id"]
        resp = await client.post(f"/api/v1/ai/messages/{umid}/cancel")
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestRegenerateMessage:
    async def _create_conv_and_send(self, client) -> dict:
        r = await client.post("/api/v1/ai/conversations", json={"title": "R"})
        cid = r.json()["data"]["id"]
        sent = await client.post(
            f"/api/v1/ai/conversations/{cid}/messages",
            json={"content": "原始问题"},
        )
        return sent.json()["data"]

    async def test_regenerate_creates_new_assistant_message(self, client):
        sent = await self._create_conv_and_send(client)
        original_amid = sent["assistant_message"]["id"]
        original_umid = sent["user_message"]["id"]
        cid = sent["conversation"]["id"]

        resp = await client.post(
            f"/api/v1/ai/messages/{original_amid}/regenerate"
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        # New assistant message has a fresh id but reuses the same user
        # prompt and conversation.
        assert body["assistant_message"]["id"] != original_amid
        assert body["user_message"]["id"] == original_umid
        assert body["conversation"]["id"] == cid
        assert body["regenerate_of"] == original_amid
        assert body["job"]["job_type"] == "ai_chat"

        # The original assistant message is still queryable in the
        # conversation detail (we don't delete history).
        detail = await client.get(f"/api/v1/ai/conversations/{cid}")
        assert detail.status_code == 200
        msg_ids = [m["id"] for m in detail.json()["data"]["messages"]]
        assert original_amid in msg_ids
        assert body["assistant_message"]["id"] in msg_ids

    async def test_regenerate_404_for_unknown_message(self, client):
        resp = await client.post(
            f"/api/v1/ai/messages/{uuid.uuid4()}/regenerate"
        )
        assert resp.status_code == 404

    async def test_regenerate_rejects_user_message(self, client):
        sent = await self._create_conv_and_send(client)
        umid = sent["user_message"]["id"]
        resp = await client.post(
            f"/api/v1/ai/messages/{umid}/regenerate"
        )
        assert resp.status_code == 400
