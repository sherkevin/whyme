"""PRD10 B-19 Skill Marketplace integration tests."""

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
import agent_os.marketplace.models  # noqa: F401
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
from agent_os.stage3.models import Skill


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
async def marketplace_seed(session_factory):
    async with session_factory() as session:
        seller = User(
            id=uuid.uuid4(),
            username="market_seller",
            email="market_seller@example.com",
            password_hash=get_password_hash("market_pass_123"),
            settings={"locale": "zh-CN"},
            is_active=True,
        )
        buyer = User(
            id=uuid.uuid4(),
            username="market_buyer",
            email="market_buyer@example.com",
            password_hash=get_password_hash("market_pass_123"),
            settings={"locale": "zh-CN"},
            is_active=True,
        )
        skill = Skill(
            id=uuid.uuid4(),
            name="竞品研究报告",
            description="输入产品和市场信息，生成结构化竞品研究报告。",
            category="research",
            steps=[{"order": 1, "name": "research", "agent_action": "summarize"}],
            version="1.0",
            status="published",
            is_active=True,
            is_installed_default=False,
            usage_count=7,
            created_by=str(seller.id),
            required_tags=["市场", "竞品"],
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
        session.add_all([seller, buyer, skill])
        await session.commit()
    return {"seller": seller, "buyer": buyer, "skill": skill}


async def _token(client: AsyncClient, username: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "market_pass_123"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_listing(client, seller_token: str, skill_id: uuid.UUID, price: int = 40):
    resp = await client.post(
        "/api/v1/skill-marketplace/listings",
        headers=_auth(seller_token),
        json={"skill_id": str(skill_id), "price_credits": price, "status": "listed"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_seller_can_list_skill_and_buyer_can_discover(client, marketplace_seed):
    seller_token = await _token(client, "market_seller")
    buyer_token = await _token(client, "market_buyer")
    listing = await _create_listing(client, seller_token, marketplace_seed["skill"].id)

    found = await client.get(
        "/api/v1/skill-marketplace/listings?keyword=竞品",
        headers=_auth(buyer_token),
    )
    assert found.status_code == 200, found.text
    items = found.json()["data"]["items"]
    assert [item["id"] for item in items] == [listing["id"]]
    assert items[0]["skill"]["name"] == "竞品研究报告"
    assert items[0]["is_installed"] is False


@pytest.mark.asyncio
async def test_purchase_installs_skill_and_consumes_real_credits(client, marketplace_seed):
    seller_token = await _token(client, "market_seller")
    buyer_token = await _token(client, "market_buyer")
    listing = await _create_listing(client, seller_token, marketplace_seed["skill"].id, price=40)

    purchase = await client.post(
        f"/api/v1/skill-marketplace/listings/{listing['id']}/purchase",
        headers=_auth(buyer_token),
    )
    assert purchase.status_code == 201, purchase.text
    data = purchase.json()["data"]
    assert data["charged_credits"] == 40
    assert data["installation"]["status"] == "installed"
    assert data["listing"]["purchases_count"] == 1

    credits = await client.get("/api/v1/billing/credits", headers=_auth(buyer_token))
    assert credits.status_code == 200, credits.text
    assert credits.json()["data"]["balance"] == 60
    assert credits.json()["data"]["items"][0]["reason"] == "skill_marketplace_purchase"

    installations = await client.get(
        "/api/v1/skill-marketplace/installations",
        headers=_auth(buyer_token),
    )
    assert installations.status_code == 200, installations.text
    assert installations.json()["data"]["items"][0]["skill"]["name"] == "竞品研究报告"


@pytest.mark.asyncio
async def test_duplicate_purchase_does_not_charge_twice(client, marketplace_seed):
    seller_token = await _token(client, "market_seller")
    buyer_token = await _token(client, "market_buyer")
    listing = await _create_listing(client, seller_token, marketplace_seed["skill"].id, price=40)

    first = await client.post(
        f"/api/v1/skill-marketplace/listings/{listing['id']}/purchase",
        headers=_auth(buyer_token),
    )
    assert first.status_code == 201, first.text
    second = await client.post(
        f"/api/v1/skill-marketplace/listings/{listing['id']}/purchase",
        headers=_auth(buyer_token),
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["already_installed"] is True
    assert second.json()["data"]["charged_credits"] == 0

    credits = await client.get("/api/v1/billing/credits", headers=_auth(buyer_token))
    assert credits.json()["data"]["balance"] == 60


@pytest.mark.asyncio
async def test_purchase_rejects_seller_and_insufficient_credits(client, marketplace_seed):
    seller_token = await _token(client, "market_seller")
    buyer_token = await _token(client, "market_buyer")
    listing = await _create_listing(client, seller_token, marketplace_seed["skill"].id, price=101)

    seller_purchase = await client.post(
        f"/api/v1/skill-marketplace/listings/{listing['id']}/purchase",
        headers=_auth(seller_token),
    )
    assert seller_purchase.status_code == 400, seller_purchase.text
    assert seller_purchase.json()["error"]["code"] == "VALIDATION_ERROR"

    buyer_purchase = await client.post(
        f"/api/v1/skill-marketplace/listings/{listing['id']}/purchase",
        headers=_auth(buyer_token),
    )
    assert buyer_purchase.status_code == 400, buyer_purchase.text
    body = buyer_purchase.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"]["balance"] == 100
    assert body["error"]["details"]["price_credits"] == 101
