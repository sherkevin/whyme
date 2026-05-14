"""Authentication API Routes Integration Tests.

Tests for authentication API endpoints:
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- GET /api/v1/auth/me
- PUT /api/v1/auth/settings

Refactored for PRD10/V1: uses ASGITransport + in-memory SQLite + dependency
overrides so the file is self-contained, doesn't require an external Postgres
or the legacy ``async_session_maker`` global, and works on httpx 0.28+.
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

# Side-effect imports so ``Base.metadata.create_all`` covers everything
# the auth router transitively touches at request time.
import agent_os.ai.models  # noqa: F401
import agent_os.conversations.models  # noqa: F401
import agent_os.db.sqlite_compat  # noqa: F401  (PG UUID -> CHAR(32))
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
from sqlalchemy import select

from agent_os.auth.models import Session, User
from agent_os.auth.security import BCRYPT_SHA256_PREFIX, get_password_hash
from agent_os.db.base import Base, get_db
from agent_os.server.app import app

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def test_engine():
    """Per-test in-memory SQLite engine with the full PRD10/PRD4 schema."""

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
        test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture
async def client(test_engine, session_factory) -> AsyncGenerator[AsyncClient, None]:
    """ASGI client that uses our test DB via ``app.dependency_overrides``."""

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
async def test_user(session_factory) -> User:
    """Seed a deterministic ``test_api_user`` for the auth flow tests."""

    async with session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            username="test_api_user",
            email="test_api@example.com",
            password_hash=get_password_hash("test_pass_123"),
            settings={"daily_goal": 10, "theme": "light", "language": "zh"},
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


# ============================================================================
# POST /api/v1/auth/register Tests
# ============================================================================


@pytest.mark.asyncio
async def test_register_success(client, session_factory):
    """Test successful user registration."""

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_new_user",
            "email": "newuser@example.com",
            "password": "newpass123",
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800

    # Verify user was created in database.
    from sqlalchemy import select

    async with session_factory() as session:
        result = await session.execute(
            select(User).where(User.username == "test_new_user")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email == "newuser@example.com"

        session_rows = (
            await session.execute(select(Session).where(Session.user_id == user.id))
        ).scalars().all()
        assert len(session_rows) == 1
        assert session_rows[0].refresh_token_hash
        assert session_rows[0].is_active is True


@pytest.mark.asyncio
async def test_register_duplicate_username(client, test_user):
    """Test registration with duplicate username."""

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_api_user",
            "email": "different@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email(client, test_user):
    """Test registration with duplicate email."""

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "different_user",
            "email": "test_api@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_email(client):
    """Test registration with invalid email."""

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_user",
            "email": "invalid-email",
            "password": "password123",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client):
    """Test registration with short password."""

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "test_user",
            "email": "test@example.com",
            "password": "12345",
        },
    )
    assert response.status_code == 422


# ============================================================================
# POST /api/v1/auth/login Tests
# ============================================================================


@pytest.mark.asyncio
async def test_login_success(client, test_user):
    """Test successful login with username."""

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_api_user", "password": "test_pass_123"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_persists_bcrypt_session(client, session_factory, test_user):
    """Password login creates a server-side refresh session without plaintext."""

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_api_user", "password": "test_pass_123"},
    )
    assert response.status_code == 200, response.text
    tokens = response.json()

    async with session_factory() as session:
        user = (
            await session.execute(select(User).where(User.username == "test_api_user"))
        ).scalar_one()
        assert user.password_hash.startswith(BCRYPT_SHA256_PREFIX)

        session_row = (
            await session.execute(select(Session).where(Session.user_id == user.id))
        ).scalar_one()
        assert session_row.token_hash != tokens["access_token"]
        assert session_row.refresh_token_hash != tokens["refresh_token"]
        assert session_row.user_agent is not None


@pytest.mark.asyncio
async def test_login_with_email(client, test_user):
    """Test successful login with email."""

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_api@example.com", "password": "test_pass_123"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client, test_user):
    """Test login with wrong password."""

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_api_user", "password": "wrong_password"},
    )
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    """Test login with non-existent user."""

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "nonexistent_user", "password": "password123"},
    )
    assert response.status_code == 401


# ============================================================================
# POST /api/v1/auth/refresh Tests
# ============================================================================


@pytest.mark.asyncio
async def test_refresh_token_success(client, test_user):
    """Test successful token refresh."""

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_api_user", "password": "test_pass_123"},
    )
    tokens = login_response.json()

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_token_is_single_use(client, test_user):
    """Refresh tokens are remembered server-side and rotated on use."""

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_api_user", "password": "test_pass_123"},
    )
    tokens = login_response.json()

    first = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert first.status_code == 200, first.text

    replay = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert replay.status_code == 401

    second = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first.json()["refresh_token"]},
    )
    assert second.status_code == 200, second.text


@pytest.mark.asyncio
async def test_refresh_token_invalid(client):
    """Test refresh with invalid token."""

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid_token_string"},
    )
    assert response.status_code == 401
    assert "Invalid refresh token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_token_missing(client):
    """Test refresh without token."""

    response = await client.post("/api/v1/auth/refresh", json={})
    assert response.status_code == 422


# ============================================================================
# GET /api/v1/auth/me Tests
# ============================================================================


@pytest.mark.asyncio
async def test_get_me_success(client, test_user):
    """Test getting current user info."""

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_api_user", "password": "test_pass_123"},
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["username"] == "test_api_user"
    assert data["email"] == "test_api@example.com"
    assert "settings" in data
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_get_me_no_token(client):
    """Test getting current user without authentication."""

    response = await client.get("/api/v1/auth/me")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    """Test getting current user with invalid token."""

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert response.status_code == 401


# ============================================================================
# PUT /api/v1/auth/settings Tests
# ============================================================================


async def _login_and_get_token(client: AsyncClient) -> str:
    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "test_api_user", "password": "test_pass_123"},
    )
    return login_response.json()["access_token"]


@pytest.mark.asyncio
async def test_update_settings_success(client, test_user):
    """Test updating user settings."""

    token = await _login_and_get_token(client)
    response = await client.put(
        "/api/v1/auth/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"settings": {"daily_goal": 20, "theme": "dark"}},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["settings"]["daily_goal"] == 20
    assert data["settings"]["theme"] == "dark"
    # Original ``language`` setting should remain (merge semantics).
    assert data["settings"].get("language") == "zh"


@pytest.mark.asyncio
async def test_update_settings_partial(client, test_user):
    """Test partial settings update."""

    token = await _login_and_get_token(client)
    response = await client.put(
        "/api/v1/auth/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"settings": {"theme": "dark"}},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["settings"]["theme"] == "dark"
    assert data["settings"].get("daily_goal") == 10


@pytest.mark.asyncio
async def test_update_settings_no_auth(client):
    """Test updating settings without authentication."""

    response = await client.put(
        "/api/v1/auth/settings",
        json={"settings": {"daily_goal": 20}},
    )
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_update_settings_add_new_field(client, test_user):
    """Test adding a new settings field."""

    token = await _login_and_get_token(client)
    response = await client.put(
        "/api/v1/auth/settings",
        headers={"Authorization": f"Bearer {token}"},
        json={"settings": {"new_field": "new_value"}},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["settings"].get("new_field") == "new_value"
    assert "daily_goal" in data["settings"]


# ============================================================================
# Integration Tests - Complete Flows
# ============================================================================


@pytest.mark.asyncio
async def test_complete_auth_flow(client):
    """Complete auth flow: register -> login -> get me -> update settings."""

    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "flow_test_user",
            "email": "flow_test@example.com",
            "password": "flowpass123",
        },
    )
    assert register_response.status_code == 201, register_response.text
    tokens = register_response.json()

    login_response = await client.post(
        "/api/v1/auth/login",
        json={"username": "flow_test_user", "password": "flowpass123"},
    )
    assert login_response.status_code == 200
    login_tokens = login_response.json()
    assert "access_token" in login_tokens

    me_response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_tokens['access_token']}"},
    )
    assert me_response.status_code == 200
    user_data = me_response.json()
    assert user_data["username"] == "flow_test_user"

    settings_response = await client.put(
        "/api/v1/auth/settings",
        headers={"Authorization": f"Bearer {login_tokens['access_token']}"},
        json={"settings": {"daily_goal": 15, "theme": "dark"}},
    )
    assert settings_response.status_code == 200
    updated_user = settings_response.json()
    assert updated_user["settings"]["daily_goal"] == 15

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    assert "access_token" in new_tokens
