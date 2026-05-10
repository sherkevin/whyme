"""PRD10 cross-user isolation regression tests.

These tests deliberately seed rows for two users and then assert that the
primary user cannot read, mutate, or discover the other user's KB, feed, AI,
SkillRun, or SearchIndex data. They are the executable audit gate for the
50-person beta prep TODO.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import agent_os.agent.models  # noqa: F401
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
import agent_os.workspaces.models  # noqa: F401
from agent_os.ai.models import (
    AIConversation,
    AIMessage,
    AIMessageRole,
    AIMessageStatus,
)
from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash
from agent_os.db.base import Base, get_db
from agent_os.jobs.models import Job, JobStatus, JobType
from agent_os.kb.models import Document, DocumentStatus, Folder
from agent_os.knowledge.models import Card
from agent_os.search_engine.models import SearchIndex
from agent_os.server.app import app
from agent_os.skills.runs import SkillRun, SkillRunStatus
from agent_os.stage3.models import Skill


@pytest_asyncio.fixture
async def isolation_engine():
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
async def isolation_session_factory(isolation_engine):
    return async_sessionmaker(
        isolation_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def client(
    isolation_session_factory,
) -> AsyncGenerator[AsyncClient, None]:
    async def _override_db():
        async with isolation_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            yield ac
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def users(isolation_session_factory):
    password = get_password_hash("isolation_pass_123")
    async with isolation_session_factory() as session:
        primary = User(
            id=uuid.uuid4(),
            username="isolation_primary",
            email="isolation_primary@example.com",
            password_hash=password,
            settings={"locale": "zh-CN"},
            is_active=True,
        )
        other = User(
            id=uuid.uuid4(),
            username="isolation_other",
            email="isolation_other@example.com",
            password_hash=password,
            settings={"locale": "zh-CN"},
            is_active=True,
        )
        session.add_all([primary, other])
        await session.commit()
    return {"primary": primary, "other": other}


@pytest_asyncio.fixture
async def seeded_private_rows(isolation_session_factory, users):
    primary = users["primary"]
    other = users["other"]
    async with isolation_session_factory() as session:
        primary_folder = Folder(
            id=uuid.uuid4(),
            user_id=primary.id,
            name="Primary Product Folder",
            description="owned by primary",
        )
        other_folder = Folder(
            id=uuid.uuid4(),
            user_id=other.id,
            name="Other Confidential Folder",
            description="owned by other",
        )
        primary_doc = Document(
            id=uuid.uuid4(),
            user_id=primary.id,
            folder_id=primary_folder.id,
            title="Primary Visible Document",
            summary="primary summary",
            content="# Primary\nVisible to primary only",
            document_type="note",
            status=DocumentStatus.READY.value,
            tags=["primary"],
        )
        other_doc = Document(
            id=uuid.uuid4(),
            user_id=other.id,
            folder_id=other_folder.id,
            title="Other Secret Document",
            summary="other summary",
            content="# Other\nShould never leak to primary",
            document_type="note",
            status=DocumentStatus.READY.value,
            tags=["other-secret"],
        )
        primary_card = Card(
            id=uuid.uuid4(),
            user_id=primary.id,
            folder_id=primary_folder.id,
            title="Primary Visible Card",
            summary="primary card summary",
            content="primary card content",
            content_type="note",
            tags=["primary"],
        )
        other_card = Card(
            id=uuid.uuid4(),
            user_id=other.id,
            folder_id=other_folder.id,
            title="Other Secret Card",
            summary="other card summary",
            content="other card content",
            content_type="note",
            tags=["other-secret"],
        )
        other_conv = AIConversation(
            id=uuid.uuid4(),
            user_id=other.id,
            title="Other Private Conversation",
            mode="general",
            context_scope={},
            message_count=1,
        )
        other_msg = AIMessage(
            id=uuid.uuid4(),
            conversation_id=other_conv.id,
            user_id=other.id,
            role=AIMessageRole.ASSISTANT.value,
            content="other assistant response",
            status=AIMessageStatus.COMPLETED.value,
        )
        skill = Skill(
            id=uuid.uuid4(),
            name="Isolation Test Skill",
            description="global skill definition",
            category="research",
            steps=[],
            version="1.0",
            status="published",
            usage_count=0,
            is_installed_default=True,
            is_active=True,
        )
        other_job = Job(
            id=uuid.uuid4(),
            user_id=other.id,
            job_type=JobType.SKILL_RUN.value,
            status=JobStatus.COMPLETED.value,
            progress=100,
            input={"skill_id": str(skill.id)},
            output={"content": "other skill output"},
        )
        other_run = SkillRun(
            id=uuid.uuid4(),
            user_id=other.id,
            skill_id=skill.id,
            job_id=other_job.id,
            status=SkillRunStatus.COMPLETED.value,
            input={"text": "other input"},
            output={"content": "other skill output"},
            save_output="kb",
        )
        primary_search = SearchIndex(
            id=uuid.uuid4(),
            item_type="document",
            item_id=primary_doc.id,
            user_id=primary.id,
            title="primary-visible-search-token",
            summary="searchable by primary",
            content="owned search row",
            tags=["primary"],
        )
        other_search = SearchIndex(
            id=uuid.uuid4(),
            item_type="document",
            item_id=other_doc.id,
            user_id=other.id,
            title="other-private-search-token",
            summary="must not be searchable by primary",
            content="private search row",
            tags=["other-secret"],
        )
        session.add_all(
            [
                primary_folder,
                other_folder,
                primary_doc,
                other_doc,
                primary_card,
                other_card,
                other_conv,
                other_msg,
                skill,
                other_job,
                other_run,
                primary_search,
                other_search,
            ]
        )
        await session.commit()

    return {
        "primary_folder": primary_folder.id,
        "other_folder": other_folder.id,
        "primary_doc": primary_doc.id,
        "other_doc": other_doc.id,
        "primary_card": primary_card.id,
        "other_card": other_card.id,
        "other_conversation": other_conv.id,
        "other_message": other_msg.id,
        "skill": skill.id,
        "other_skill_run": other_run.id,
    }


async def _token(client: AsyncClient, username: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "isolation_pass_123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _assert_not_found(resp) -> None:
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_kb_documents_and_folders_are_user_scoped(
    client, seeded_private_rows
):
    token = await _token(client, "isolation_primary")
    headers = _auth(token)
    rows = seeded_private_rows

    await _assert_not_found(
        await client.get(f"/api/v1/kb/folders/{rows['other_folder']}", headers=headers)
    )
    await _assert_not_found(
        await client.get(f"/api/v1/kb/documents/{rows['other_doc']}", headers=headers)
    )
    await _assert_not_found(
        await client.patch(
            f"/api/v1/kb/documents/{rows['other_doc']}",
            headers=headers,
            json={"title": "stolen rename"},
        )
    )
    await _assert_not_found(
        await client.delete(
            f"/api/v1/kb/documents/{rows['other_doc']}",
            headers=headers,
        )
    )
    await _assert_not_found(
        await client.post(
            f"/api/v1/kb/documents/{rows['primary_doc']}/move",
            headers=headers,
            json={"target_folder_id": str(rows["other_folder"])},
        )
    )


@pytest.mark.asyncio
async def test_feed_cards_are_user_scoped(client, seeded_private_rows):
    token = await _token(client, "isolation_primary")
    headers = _auth(token)
    rows = seeded_private_rows

    await _assert_not_found(
        await client.get(f"/api/v1/cards/{rows['other_card']}", headers=headers)
    )
    await _assert_not_found(
        await client.patch(
            f"/api/v1/cards/{rows['other_card']}",
            headers=headers,
            json={"title": "stolen card rename"},
        )
    )
    await _assert_not_found(
        await client.post(
            f"/api/v1/cards/{rows['other_card']}/favorite",
            headers=headers,
            json={"is_favorite": True},
        )
    )
    await _assert_not_found(
        await client.post(
            f"/api/v1/cards/{rows['other_card']}/ai-summary",
            headers=headers,
        )
    )
    await _assert_not_found(
        await client.delete(f"/api/v1/cards/{rows['other_card']}", headers=headers)
    )
    await _assert_not_found(
        await client.post(
            f"/api/v1/cards/{rows['primary_card']}/move",
            headers=headers,
            json={"target_folder_id": str(rows["other_folder"])},
        )
    )


@pytest.mark.asyncio
async def test_ai_conversations_and_message_actions_are_user_scoped(
    client, seeded_private_rows
):
    token = await _token(client, "isolation_primary")
    headers = _auth(token)
    rows = seeded_private_rows

    await _assert_not_found(
        await client.get(
            f"/api/v1/ai/conversations/{rows['other_conversation']}",
            headers=headers,
        )
    )
    await _assert_not_found(
        await client.get(f"/api/v1/ai/messages/{rows['other_message']}", headers=headers)
    )
    await _assert_not_found(
        await client.post(
            f"/api/v1/ai/messages/{rows['other_message']}/save-to-kb",
            headers=headers,
            json={},
        )
    )
    await _assert_not_found(
        await client.post(
            f"/api/v1/ai/messages/{rows['other_message']}/cancel",
            headers=headers,
        )
    )
    await _assert_not_found(
        await client.post(
            f"/api/v1/ai/messages/{rows['other_message']}/regenerate",
            headers=headers,
        )
    )


@pytest.mark.asyncio
async def test_skill_runs_are_user_scoped(client, seeded_private_rows):
    token = await _token(client, "isolation_primary")
    headers = _auth(token)
    rows = seeded_private_rows

    await _assert_not_found(
        await client.get(
            f"/api/v1/skills/runs/{rows['other_skill_run']}",
            headers=headers,
        )
    )

    history = await client.get(
        f"/api/v1/skills/{rows['skill']}/runs",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    assert history.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_search_and_suggestions_do_not_leak_other_user_rows(
    client, seeded_private_rows
):
    token = await _token(client, "isolation_primary")
    headers = _auth(token)

    own = await client.get(
        "/api/v1/search",
        headers=headers,
        params={"q": "primary-visible-search-token"},
    )
    assert own.status_code == 200, own.text
    assert [item["title"] for item in own.json()["data"]["items"]] == [
        "primary-visible-search-token"
    ]

    leaked = await client.get(
        "/api/v1/search",
        headers=headers,
        params={"q": "other-private-search-token"},
    )
    assert leaked.status_code == 200, leaked.text
    assert leaked.json()["data"]["items"] == []

    suggestions = await client.get(
        "/api/v1/search/suggestions",
        headers=headers,
        params={"q": "other-private"},
    )
    assert suggestions.status_code == 200, suggestions.text
    assert suggestions.json()["data"]["suggestions"] == []
