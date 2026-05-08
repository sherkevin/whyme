"""
PRD10 §15.28 — `/api/v1/demo/{status,login}` envelope contract regression.

These tests pin the response shape so a future refactor cannot quietly
strip the PRD10 success envelope from the demo bypass endpoints. Without
the envelope, any client that follows the standard PRD10 contract
(`{success, data, request_id}` for 2xx, `{success: false, error}` for
4xx/5xx) silently breaks demo auto-login — exactly what bridge.js tripped
over before §15.28 was filed.

Guards:
    * `GET /api/v1/demo/status` envelope shape
    * `POST /api/v1/demo/login` envelope shape (token fields under data)
    * `POST /api/v1/demo/login` 403 PRD10 error envelope when demo mode off
    * Round-trip: token from envelope.data is usable on `/api/v1/me`
"""
from __future__ import annotations

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

# Side-effect imports so ``Base.metadata.create_all`` covers everything
# that PRD10 expects (mirrors test_prd10_frontend_binding fixtures).
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
from agent_os.db.base import Base, get_db
from agent_os.server.app import app as prd_app

# ---------------------------------------------------------------------------
# Fixtures (mirror test_prd10_frontend_binding so isolation is identical).
# These tests intentionally do NOT inject a ``fixture_user`` — demo/login
# creates its own ``demo@mydow.example`` user lazily. ``client_no_auth_override``
# only overrides ``get_db`` so the auth dependency stays real.
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
async def client(prd10_engine) -> AsyncGenerator[AsyncClient, None]:
    factory = async_sessionmaker(
        prd10_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_db():
        async with factory() as session:
            yield session

    prd_app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=prd_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        try:
            yield ac
        finally:
            prd_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Status envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_returns_prd10_envelope_when_demo_off(monkeypatch, client):
    monkeypatch.delenv("AGENTOS_DEMO_MODE", raising=False)

    resp = await client.get("/api/v1/demo/status")
    assert resp.status_code == 200

    body = resp.json()
    assert isinstance(body, dict)
    assert set(body.keys()) >= {"success", "data", "request_id"}, body
    assert body["success"] is True
    assert isinstance(body["request_id"], str) and body["request_id"].startswith("req_")

    data = body["data"]
    assert data["enabled"] is False
    assert data["email"] is None
    # Defensive: top-level must not duplicate the inner fields
    assert "enabled" not in body
    assert "email" not in body


@pytest.mark.asyncio
async def test_status_returns_prd10_envelope_when_demo_on(monkeypatch, client):
    monkeypatch.setenv("AGENTOS_DEMO_MODE", "on")

    resp = await client.get("/api/v1/demo/status")
    assert resp.status_code == 200

    body = resp.json()
    assert body["success"] is True
    assert body["data"]["enabled"] is True
    assert body["data"]["email"] == "demo@mydow.example"
    assert "enabled" not in body, "envelope must not duplicate fields at top level"


# ---------------------------------------------------------------------------
# Login envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_returns_prd10_envelope(monkeypatch, client):
    monkeypatch.setenv("AGENTOS_DEMO_MODE", "on")

    resp = await client.post("/api/v1/demo/login")
    assert resp.status_code == 200

    body = resp.json()
    assert isinstance(body, dict)
    assert set(body.keys()) >= {"success", "data", "request_id"}, body
    assert body["success"] is True
    assert isinstance(body["request_id"], str) and body["request_id"].startswith("req_")

    data = body["data"]
    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str) and len(data["access_token"]) > 50
    assert isinstance(data["refresh_token"], str) and len(data["refresh_token"]) > 50
    assert data["expires_in"] == 30 * 60

    # Defensive: top level must not duplicate the token fields
    assert "access_token" not in body
    assert "refresh_token" not in body


@pytest.mark.asyncio
async def test_login_403_uses_prd10_error_envelope(monkeypatch, client):
    monkeypatch.delenv("AGENTOS_DEMO_MODE", raising=False)

    resp = await client.post("/api/v1/demo/login")
    assert resp.status_code == 403

    body = resp.json()
    assert isinstance(body, dict)
    assert body.get("success") is False
    assert "error" in body and isinstance(body["error"], dict)
    err_code = body["error"].get("code") or ""
    assert err_code in {"FORBIDDEN", "forbidden"}, body["error"]
    assert isinstance(body["error"].get("message"), str) and body["error"]["message"]
    assert body.get("request_id", "").startswith("req_")


# ---------------------------------------------------------------------------
# End-to-end: token from envelope is actually usable against /me.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_envelope_token_round_trips_to_me(monkeypatch, client):
    """The wrapping change must not break the JWT itself — ``/me`` should
    accept the freshly minted access token without complaint."""
    monkeypatch.setenv("AGENTOS_DEMO_MODE", "on")

    login = await client.post("/api/v1/demo/login")
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    assert token

    me = await client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200, me.text
    me_body = me.json()
    # ``GET /api/v1/me`` returns legacy flat ``Prd10MeResponse`` JSON in the
    # full app; envelope-wrapped success is reserved for list endpoints that
    # already call ``success_response``. Accept either shape here.
    me_data = me_body["data"] if me_body.get("success") is True else me_body
    assert me_data["email"] == "demo@mydow.example"
