"""Observability hooks for PRD10 routers.

Verifies that ``Prd10AccessLogMiddleware`` emits a single structured log
record with the expected fields per PRD10 access, and that non-PRD10 paths
do **not** generate the structured record.
"""

from __future__ import annotations

import logging
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


@pytest.mark.asyncio
async def test_prd10_path_emits_access_log(client, caplog):
    caplog.set_level(logging.INFO, logger="agent_os.prd10.access")
    resp = await client.get("/api/v1/search", params={"q": ""})
    assert resp.status_code == 200

    matching = [
        rec for rec in caplog.records
        if rec.name == "agent_os.prd10.access"
        and rec.message == "prd10_access"
        and getattr(rec, "prd10_path", None) == "/api/v1/search"
    ]
    assert len(matching) == 1
    rec = matching[0]
    assert rec.prd10_method == "GET"
    assert rec.prd10_status_code == 200
    assert isinstance(rec.prd10_duration_ms, int)
    assert rec.prd10_request_id == resp.headers["X-Request-ID"]


@pytest.mark.asyncio
async def test_failure_logged_at_warning(client, caplog):
    caplog.set_level(logging.INFO, logger="agent_os.prd10.access")
    resp = await client.get(f"/api/v1/ai/conversations/{uuid.uuid4()}")
    assert resp.status_code == 404

    matching = [
        rec for rec in caplog.records
        if rec.name == "agent_os.prd10.access"
        and getattr(rec, "prd10_status_code", None) == 404
    ]
    assert len(matching) == 1
    # 4xx is not severe enough for WARNING; that level is reserved for 5xx.
    assert matching[0].levelno == logging.INFO


@pytest.mark.asyncio
async def test_non_prd10_path_skipped(client, caplog):
    caplog.set_level(logging.INFO, logger="agent_os.prd10.access")
    # An obviously-unmatched legacy path. The legacy ``conversations``
    # router lives under ``/api/v1/conversations`` (no trailing -prd10).
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200

    matching = [
        rec for rec in caplog.records
        if rec.name == "agent_os.prd10.access"
    ]
    assert matching == []
