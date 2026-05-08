"""PRD10 B-17 workspace permission integration tests."""

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
from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash
from agent_os.db.base import Base, get_db
from agent_os.server.app import app


@pytest_asyncio.fixture
async def test_engine():
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
async def session_factory(test_engine):
    return async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def client(test_engine, session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def _override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            yield ac
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest_asyncio.fixture
async def users(session_factory):
    password = get_password_hash("workspace_pass_123")
    async with session_factory() as session:
        owner = User(
            id=uuid.uuid4(),
            username="workspace_owner",
            email="workspace_owner@example.com",
            password_hash=password,
            settings={"locale": "zh-CN"},
            is_active=True,
        )
        member = User(
            id=uuid.uuid4(),
            username="workspace_member",
            email="workspace_member@example.com",
            password_hash=password,
            settings={"locale": "zh-CN"},
            is_active=True,
        )
        outsider = User(
            id=uuid.uuid4(),
            username="workspace_outsider",
            email="workspace_outsider@example.com",
            password_hash=password,
            settings={"locale": "zh-CN"},
            is_active=True,
        )
        session.add_all([owner, member, outsider])
        await session.commit()
    return {"owner": owner, "member": member, "outsider": outsider}


async def _token(client: AsyncClient, username: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "workspace_pass_123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_workspace_owner_can_create_and_list(client, users):
    owner_token = await _token(client, "workspace_owner")

    created = await client.post(
        "/api/v1/workspaces",
        headers=_auth(owner_token),
        json={"name": "Growth Lab", "description": "Team knowledge space"},
    )
    assert created.status_code == 201, created.text
    data = created.json()["data"]
    assert data["name"] == "Growth Lab"
    assert data["role"] == "owner"

    listed = await client.get("/api/v1/workspaces", headers=_auth(owner_token))
    assert listed.status_code == 200, listed.text
    items = listed.json()["data"]["items"]
    assert [item["id"] for item in items] == [data["id"]]
    assert items[0]["role"] == "owner"


@pytest.mark.asyncio
async def test_workspace_non_member_gets_explicit_403(client, users):
    owner_token = await _token(client, "workspace_owner")
    outsider_token = await _token(client, "workspace_outsider")
    created = await client.post(
        "/api/v1/workspaces",
        headers=_auth(owner_token),
        json={"name": "Private Workspace"},
    )
    workspace_id = created.json()["data"]["id"]

    denied = await client.get(
        f"/api/v1/workspaces/{workspace_id}",
        headers=_auth(outsider_token),
    )
    assert denied.status_code == 403, denied.text
    body = denied.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_viewer_can_read_but_cannot_admin_until_promoted(client, users):
    owner_token = await _token(client, "workspace_owner")
    member_token = await _token(client, "workspace_member")
    created = await client.post(
        "/api/v1/workspaces",
        headers=_auth(owner_token),
        json={"name": "Shared Workspace"},
    )
    workspace_id = created.json()["data"]["id"]

    invited = await client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        headers=_auth(owner_token),
        json={"email": users["member"].email, "role": "viewer"},
    )
    assert invited.status_code == 201, invited.text
    assert invited.json()["data"]["role"] == "viewer"

    visible = await client.get(
        f"/api/v1/workspaces/{workspace_id}",
        headers=_auth(member_token),
    )
    assert visible.status_code == 200, visible.text
    assert visible.json()["data"]["role"] == "viewer"

    forbidden_patch = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        headers=_auth(member_token),
        json={"name": "Viewer Rename"},
    )
    assert forbidden_patch.status_code == 403, forbidden_patch.text
    assert forbidden_patch.json()["error"]["code"] == "FORBIDDEN"

    promoted = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{users['member'].id}",
        headers=_auth(owner_token),
        json={"role": "admin"},
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["data"]["role"] == "admin"

    allowed_patch = await client.patch(
        f"/api/v1/workspaces/{workspace_id}",
        headers=_auth(member_token),
        json={"name": "Admin Rename"},
    )
    assert allowed_patch.status_code == 200, allowed_patch.text
    assert allowed_patch.json()["data"]["name"] == "Admin Rename"


@pytest.mark.asyncio
async def test_workspace_owner_cannot_be_removed_or_downgraded(client, users):
    owner_token = await _token(client, "workspace_owner")
    created = await client.post(
        "/api/v1/workspaces",
        headers=_auth(owner_token),
        json={"name": "Owner Guard"},
    )
    workspace_id = created.json()["data"]["id"]

    downgrade = await client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{users['owner'].id}",
        headers=_auth(owner_token),
        json={"role": "viewer"},
    )
    assert downgrade.status_code == 400, downgrade.text
    assert downgrade.json()["error"]["code"] == "VALIDATION_ERROR"

    remove = await client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{users['owner'].id}",
        headers=_auth(owner_token),
    )
    assert remove.status_code == 400, remove.text
    assert remove.json()["error"]["code"] == "VALIDATION_ERROR"
