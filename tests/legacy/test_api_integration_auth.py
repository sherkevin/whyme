"""API integration tests for Authentication endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.test_app import test_app as app

from agent_os.db.base import Base
from agent_os.db.session import get_db

# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
async def in_memory_db():
    """Create in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest.fixture
async def db_session(in_memory_db):
    """Create async database session for testing."""
    async_session_maker = async_sessionmaker(
        bind=in_memory_db,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_maker() as session:
        yield session


@pytest.fixture
def test_client(db_session):
    """Create test client with database session override."""
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Override both get_db functions (from db.base and db.session)
    from agent_os.db import base as db_base
    app.dependency_overrides[db_base.get_db] = override_get_db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# =============================================================================
# Authentication API Tests
# =============================================================================

class TestRegistrationAPI:
    """Test user registration API."""

    def test_register_user_success(self, test_client):
        """Test successful user registration."""
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "password123"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"

    def test_register_user_duplicate_username(self, test_client):
        """Test registration with duplicate username."""
        # Register first user
        test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "user1@example.com",
                "password": "password123"
            }
        )

        # Try to register with same username
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "user2@example.com",
                "password": "password123"
            }
        )

        assert response.status_code == 400

    def test_register_user_duplicate_email(self, test_client):
        """Test registration with duplicate email."""
        # Register first user
        test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "user1",
                "email": "test@example.com",
                "password": "password123"
            }
        )

        # Try to register with same email
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "user2",
                "email": "test@example.com",
                "password": "password123"
            }
        )

        assert response.status_code == 400

    def test_register_user_invalid_email(self, test_client):
        """Test registration with invalid email."""
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "invalid-email",
                "password": "password123"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_register_user_weak_password(self, test_client):
        """Test registration with weak password."""
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "short"  # Too short
            }
        )

        assert response.status_code == 422

    def test_register_user_creates_settings(self, test_client):
        """Test that registration creates default user settings."""
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data


class TestLoginAPI:
    """Test user login API."""

    def test_login_with_username_success(self, test_client):
        """Test successful login with username."""
        # Register user first
        test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123"
            }
        )

        # Login
        response = test_client.post(
            "/api/v1/auth/login",
            data={
                "username": "testuser",
                "password": "password123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_with_email_success(self, test_client):
        """Test successful login with email."""
        # Register user first
        test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123"
            }
        )

        # Login with email
        response = test_client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",  # Using email as username
                "password": "password123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_wrong_password(self, test_client):
        """Test login with wrong password."""
        # Register user first
        test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123"
            }
        )

        # Login with wrong password
        response = test_client.post(
            "/api/v1/auth/login",
            data={
                "username": "testuser",
                "password": "wrongpassword"
            }
        )

        assert response.status_code == 401

    def test_login_nonexistent_user(self, test_client):
        """Test login with non-existent user."""
        response = test_client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent",
                "password": "password123"
            }
        )

        assert response.status_code == 401

    def test_login_missing_fields(self, test_client):
        """Test login with missing fields."""
        response = test_client.post(
            "/api/v1/auth/login",
            data={
                "username": "testuser"
                # Missing password
            }
        )

        assert response.status_code == 422


class TestTokenRefreshAPI:
    """Test token refresh API."""

    def test_refresh_token_success(self, test_client):
        """Test successful token refresh."""
        # Register and login
        test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123"
            }
        )

        login_response = test_client.post(
            "/api/v1/auth/login",
            data={
                "username": "testuser",
                "password": "password123"
            }
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        response = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_token_invalid(self, test_client):
        """Test refresh with invalid token."""
        response = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )

        assert response.status_code == 401


class TestUserInfoAPI:
    """Test user info API."""

    @pytest.fixture
    def auth_headers(self, test_client):
        """Get authentication headers."""
        # Register user
        test_client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123"
            }
        )

        # Login
        response = test_client.post(
            "/api/v1/auth/login",
            data={
                "username": "testuser",
                "password": "password123"
            }
        )

        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_get_current_user_info(self, test_client, auth_headers):
        """Test getting current user info."""
        response = test_client.get(
            "/api/v1/auth/users/me",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "username" in data
        assert "email" in data
        assert data["username"] == "testuser"

    def test_get_current_user_info_unauthorized(self, test_client):
        """Test getting user info without authentication."""
        response = test_client.get("/api/v1/auth/users/me")

        assert response.status_code == 401

    def test_update_user_settings(self, test_client, auth_headers):
        """Test updating user settings."""
        response = test_client.put(
            "/api/v1/auth/users/settings",
            json={
                "daily_goal": 15,
                "theme": "dark"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["daily_goal"] == 15
        assert data["theme"] == "dark"

    def test_update_user_settings_invalid_goal(self, test_client, auth_headers):
        """Test updating settings with invalid daily_goal."""
        response = test_client.put(
            "/api/v1/auth/users/settings",
            json={"daily_goal": 200},  # Too high
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_update_user_settings_invalid_theme(self, test_client, auth_headers):
        """Test updating settings with invalid theme."""
        response = test_client.put(
            "/api/v1/auth/users/settings",
            json={"theme": "invalid_theme"},
            headers=auth_headers
        )

        assert response.status_code == 422
