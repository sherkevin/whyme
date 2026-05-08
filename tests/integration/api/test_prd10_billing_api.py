"""PRD10 B-18 subscription and credit ledger integration tests."""

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
import agent_os.billing.models  # noqa: F401
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
async def billing_user(session_factory):
    async with session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            username="billing_user",
            email="billing_user@example.com",
            password_hash=get_password_hash("billing_pass_123"),
            settings={"locale": "zh-CN"},
            is_active=True,
        )
        session.add(user)
        await session.commit()
    return user


async def _token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "billing_user", "password": "billing_pass_123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_billing_plans_and_default_overview_are_real(client, billing_user):
    token = await _token(client)

    plans = await client.get("/api/v1/billing/plans", headers=_auth(token))
    assert plans.status_code == 200, plans.text
    plan_codes = [item["code"] for item in plans.json()["data"]["items"]]
    assert plan_codes == ["free", "pro", "team", "enterprise"]

    overview = await client.get("/api/v1/billing/overview", headers=_auth(token))
    assert overview.status_code == 200, overview.text
    data = overview.json()["data"]
    assert data["subscription"]["plan"] == "free"
    assert data["credit_balance"] == 100
    assert data["recent_transactions"][0]["reason"] == "initial_plan_allowance"


@pytest.mark.asyncio
async def test_subscription_upgrade_persists_plan_and_credit_ledger(client, billing_user):
    token = await _token(client)
    await client.get("/api/v1/billing/overview", headers=_auth(token))

    upgraded = await client.patch(
        "/api/v1/billing/subscription",
        headers=_auth(token),
        json={"plan": "pro", "billing_cycle": "yearly"},
    )
    assert upgraded.status_code == 200, upgraded.text
    assert upgraded.json()["data"]["plan"] == "pro"
    assert upgraded.json()["data"]["billing_cycle"] == "yearly"

    me = await client.get("/api/v1/me", headers=_auth(token))
    assert me.status_code == 200, me.text
    me_data = me.json().get("data") or me.json()
    assert me_data["plan"] == "pro"
    assert me_data["settings"]["plan"] == "pro"

    credits = await client.get("/api/v1/billing/credits", headers=_auth(token))
    assert credits.status_code == 200, credits.text
    data = credits.json()["data"]
    assert data["balance"] == 1100
    assert [item["reason"] for item in data["items"][:2]] == [
        "plan_allowance",
        "initial_plan_allowance",
    ]


@pytest.mark.asyncio
async def test_credit_consumption_records_negative_ledger_entry(client, billing_user):
    token = await _token(client)
    await client.get("/api/v1/billing/overview", headers=_auth(token))

    consumed = await client.post(
        "/api/v1/billing/credits/consume",
        headers=_auth(token),
        json={
            "amount": 25,
            "reason": "ai_message",
            "reference_type": "ai_message",
            "reference_id": "msg_123",
        },
    )
    assert consumed.status_code == 201, consumed.text
    entry = consumed.json()["data"]
    assert entry["amount"] == -25
    assert entry["balance_after"] == 75
    assert entry["reference_id"] == "msg_123"

    credits = await client.get("/api/v1/billing/credits", headers=_auth(token))
    assert credits.json()["data"]["balance"] == 75
    assert credits.json()["data"]["items"][0]["reason"] == "ai_message"


@pytest.mark.asyncio
async def test_credit_consumption_rejects_insufficient_balance(client, billing_user):
    token = await _token(client)
    await client.get("/api/v1/billing/overview", headers=_auth(token))

    rejected = await client.post(
        "/api/v1/billing/credits/consume",
        headers=_auth(token),
        json={"amount": 101, "reason": "overspend"},
    )
    assert rejected.status_code == 400, rejected.text
    body = rejected.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["balance"] == 100
