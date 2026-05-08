"""PRD10 app-wiring smoke tests.

Loads the full ``agent_os.server.app`` and asserts that:

1. The PRD10 intelligence routers (Agent 3) are mounted under their PRD10 paths.
2. The ``X-Request-ID`` header round-trips via ``RequestIdMiddleware``.
3. PRD10 envelope error format applies for ``/api/v1/search``, ``/api/v1/ai``,
   ``/api/v1/skills``, ``/api/v1/garden`` (per ``_PRD10_ENVELOPE_PREFIXES``).

We do **not** spin up a real DB. Auth is overridden to inject a fixture user;
DB calls are short-circuited by patching ``get_db`` with a session that uses
the same StaticPool/in-memory engine the other PRD10 tests use, so the smoke
test only verifies wiring rather than business logic.
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

# Side-effect imports so ``Base.metadata`` covers every PRD10 / PRD4 table
# referenced transitively by the routers we mount below.
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
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAppWiring:
    async def test_search_route_mounted(self, client):
        resp = await client.get("/api/v1/search", params={"q": ""})
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["items"] == []
        # RequestIdMiddleware must echo the header.
        assert resp.headers.get("X-Request-ID")
        assert resp.headers["X-Request-ID"] == body["request_id"]

    async def test_ai_conversations_route_mounted(self, client):
        resp = await client.get("/api/v1/ai/conversations")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["items"] == []
        assert resp.headers.get("X-Request-ID")

    async def test_skills_route_mounted(self, client):
        resp = await client.get("/api/v1/skills")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        # Agent 3's ``_ensure_default_skill`` lazily seeds one built-in skill
        # on first hit so a fresh V1 install always has something runnable;
        # an empty list is no longer the only acceptable shape, but every
        # entry must still carry the PRD10 §5.13 DTO fields.
        for item in body["data"]["items"]:
            assert "id" in item
            assert "name" in item
        assert resp.headers.get("X-Request-ID")

    async def test_garden_overview_mounted(self, client):
        resp = await client.get("/api/v1/garden/overview")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["node_count"] == 0
        assert data["edge_count"] == 0

    async def test_request_id_round_trip(self, client):
        custom_id = "req_inbound_test_xyz"
        resp = await client.get(
            "/api/v1/search",
            params={"q": ""},
            headers={"X-Request-ID": custom_id},
        )
        assert resp.headers.get("X-Request-ID") == custom_id
        assert resp.json()["request_id"] == custom_id

    async def test_404_uses_prd10_envelope_for_intelligence_paths(self, client):
        resp = await client.get(
            f"/api/v1/ai/conversations/{uuid.uuid4()}"
        )
        assert resp.status_code == 404
        body = resp.json()
        # PRD10 envelope from app's HTTPException handler.
        assert body["success"] is False
        assert body["error"]["code"] == "NOT_FOUND"
        assert body["request_id"].startswith("req_")


@pytest.mark.asyncio
class TestPrd10Cors:
    """PRD10 §11.4 CORS — validate the strict-by-default policy declared in
    ``agent_os/server/app.py`` (Engineer 1 / §11.4 doing → done).

    The defaults whitelist common dev origins (``http://localhost:3000`` /
    ``5173`` / ``8000`` / ``8770``). Production sets ``AGENTOS_CORS_ORIGINS``
    to a strict list. We exercise both the simple-request path (GET with
    ``Origin``) and a preflight (``OPTIONS`` with ``Access-Control-Request-*``).
    """

    async def test_preflight_allows_dev_origin(self, client):
        resp = await client.options(
            "/api/v1/search",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization,Content-Type,X-Request-ID",
            },
        )
        assert resp.status_code in (200, 204)
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        allow_methods = (resp.headers.get("access-control-allow-methods") or "").upper()
        for verb in ("GET", "POST", "DELETE", "PATCH"):
            assert verb in allow_methods
        allow_headers = (resp.headers.get("access-control-allow-headers") or "").lower()
        assert "authorization" in allow_headers
        assert "x-request-id" in allow_headers
        assert resp.headers.get("access-control-allow-credentials") == "true"

    async def test_simple_request_echoes_allowed_origin(self, client):
        resp = await client.get(
            "/api/v1/search",
            params={"q": ""},
            headers={"Origin": "http://localhost:5173"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
        expose = (resp.headers.get("access-control-expose-headers") or "").lower()
        assert "x-request-id" in expose

    async def test_unknown_origin_is_not_echoed(self, client):
        resp = await client.options(
            "/api/v1/search",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.headers.get("access-control-allow-origin") not in (
            "https://attacker.example",
            "*",
        )

    async def test_request_id_round_trips_with_cors(self, client):
        custom_id = "req_cors_round_trip"
        resp = await client.get(
            "/api/v1/search",
            params={"q": ""},
            headers={
                "Origin": "http://localhost:3000",
                "X-Request-ID": custom_id,
            },
        )
        assert resp.headers.get("X-Request-ID") == custom_id
        expose = (resp.headers.get("access-control-expose-headers") or "").lower()
        assert "x-request-id" in expose
        assert resp.json()["request_id"] == custom_id
