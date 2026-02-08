"""Authentication API Routes Integration Tests.

Tests for authentication API endpoints:
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- GET /api/v1/auth/me
- PUT /api/v1/auth/settings
"""

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from agent_os.db.base import get_db, async_session_maker
from agent_os.auth.models import User
from agent_os.auth.router import router
from agent_os.auth.security import verify_password
from agent_os.main import app


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
async def cleanup_users():
    """Cleanup test users after tests."""
    yield
    async with async_session_maker() as session:
        await session.execute("DELETE FROM users WHERE username LIKE 'test_%'")
        await session.commit()


@pytest.fixture
async def test_user(cleanup_users):
    """Create a test user."""
    async with async_session_maker() as session:
        from agent_os.auth.security import get_password_hash

        user = User(
            username="test_api_user",
            email="test_api@example.com",
            password_hash=get_password_hash("test_pass_123"),
            settings={"daily_goal": 10, "theme": "light", "language": "zh"}
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


# ============================================================================
# POST /api/v1/auth/register Tests
# ============================================================================

@pytest.mark.asyncio
async def test_register_success(cleanup_users):
    """Test successful user registration."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "test_new_user",
                "email": "newuser@example.com",
                "password": "newpass123"
            }
        )

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800  # 30 minutes

    # Verify user was created in database
    async with async_session_maker() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(User).filter(User.username == "test_new_user")
        )
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.email == "newuser@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_username(test_user):
    """Test registration with duplicate username."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "test_api_user",  # Already exists
                "email": "different@example.com",
                "password": "password123"
            }
        )

    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_email(test_user):
    """Test registration with duplicate email."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "different_user",
                "email": "test_api@example.com",  # Already exists
                "password": "password123"
            }
        )

    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_invalid_email(cleanup_users):
    """Test registration with invalid email."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "test_user",
                "email": "invalid-email",
                "password": "password123"
            }
        )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_register_short_password(cleanup_users):
    """Test registration with short password."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "test_user",
                "email": "test@example.com",
                "password": "12345"  # Too short (min 6)
            }
        )

    assert response.status_code == 422  # Validation error


# ============================================================================
# POST /api/v1/auth/login Tests
# ============================================================================

@pytest.mark.asyncio
async def test_login_success(test_user):
    """Test successful login with username."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test_api_user",
                "password": "test_pass_123"
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_with_email(test_user):
    """Test successful login with email."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test_api@example.com",  # Email as username
                "password": "test_pass_123"
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(test_user):
    """Test login with wrong password."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test_api_user",
                "password": "wrong_password"
            }
        )

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(cleanup_users):
    """Test login with non-existent user."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent_user",
                "password": "password123"
            }
        )

    assert response.status_code == 401


# ============================================================================
# POST /api/v1/auth/refresh Tests
# ============================================================================

@pytest.mark.asyncio
async def test_refresh_token_success(test_user):
    """Test successful token refresh."""
    # First login to get tokens
    async with AsyncClient(app=app, base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test_api_user",
                "password": "test_pass_123"
            }
        )
        tokens = login_response.json()

        # Use refresh token to get new tokens
        response = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": tokens["refresh_token"]
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_token_invalid():
    """Test refresh with invalid token."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "invalid_token_string"
            }
        )

    assert response.status_code == 401
    assert "Invalid refresh token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_refresh_token_missing():
    """Test refresh without token."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/refresh",
            json={}
        )

    assert response.status_code == 422  # Validation error


# ============================================================================
# GET /api/v1/auth/me Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_me_success(test_user):
    """Test getting current user info."""
    # First login to get token
    async with AsyncClient(app=app, base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test_api_user",
                "password": "test_pass_123"
            }
        )
        token = login_response.json()["access_token"]

        # Get current user info
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "test_api_user"
    assert data["email"] == "test_api@example.com"
    assert "settings" in data
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_get_me_no_token():
    """Test getting current user without authentication."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token():
    """Test getting current user with invalid token."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )

    assert response.status_code == 401


# ============================================================================
# PUT /api/v1/auth/settings Tests
# ============================================================================

@pytest.mark.asyncio
async def test_update_settings_success(test_user):
    """Test updating user settings."""
    # Login to get token
    async with AsyncClient(app=app, base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test_api_user",
                "password": "test_pass_123"
            }
        )
        token = login_response.json()["access_token"]

        # Update settings
        response = await client.put(
            "/api/v1/auth/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "settings": {
                    "daily_goal": 20,
                    "theme": "dark"
                }
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["daily_goal"] == 20
    assert data["settings"]["theme"] == "dark"
    # Other settings should remain
    assert data["settings"]["language"] == "zh"


@pytest.mark.asyncio
async def test_update_settings_partial(test_user):
    """Test partial settings update."""
    # Login to get token
    async with AsyncClient(app=app, base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test_api_user",
                "password": "test_pass_123"
            }
        )
        token = login_response.json()["access_token"]

        # Update only one setting
        response = await client.put(
            "/api/v1/auth/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "settings": {
                    "theme": "dark"
                }
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["theme"] == "dark"
    # Other settings should remain unchanged
    assert data["settings"]["daily_goal"] == 10


@pytest.mark.asyncio
async def test_update_settings_no_auth():
    """Test updating settings without authentication."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/api/v1/auth/settings",
            json={
                "settings": {
                    "daily_goal": 20
                }
            }
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_settings_add_new_field(test_user):
    """Test adding a new settings field."""
    # Login to get token
    async with AsyncClient(app=app, base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test_api_user",
                "password": "test_pass_123"
            }
        )
        token = login_response.json()["access_token"]

        # Add a new field
        response = await client.put(
            "/api/v1/auth/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "settings": {
                    "new_field": "new_value"
                }
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert data["settings"]["new_field"] == "new_value"
    # Original fields should remain
    assert "daily_goal" in data["settings"]


# ============================================================================
# Integration Tests - Complete Flows
# ============================================================================

@pytest.mark.asyncio
async def test_complete_auth_flow(cleanup_users):
    """Test complete authentication flow: register -> login -> get me -> update settings."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Register
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "flow_test_user",
                "email": "flow_test@example.com",
                "password": "flowpass123"
            }
        )
        assert register_response.status_code == 201
        tokens = register_response.json()

        # 2. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "flow_test_user",
                "password": "flowpass123"
            }
        )
        assert login_response.status_code == 200
        login_tokens = login_response.json()
        assert "access_token" in login_tokens

        # 3. Get current user
        me_response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {login_tokens['access_token']}"}
        )
        assert me_response.status_code == 200
        user_data = me_response.json()
        assert user_data["username"] == "flow_test_user"

        # 4. Update settings
        settings_response = await client.put(
            "/api/v1/auth/settings",
            headers={"Authorization": f"Bearer {login_tokens['access_token']}"},
            json={
                "settings": {
                    "daily_goal": 15,
                    "theme": "dark"
                }
            }
        )
        assert settings_response.status_code == 200
        updated_user = settings_response.json()
        assert updated_user["settings"]["daily_goal"] == 15

        # 5. Refresh token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": tokens["refresh_token"]
            }
        )
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens


# ============================================================================
# End of Tests
# ============================================================================
