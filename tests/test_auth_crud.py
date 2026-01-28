"""Test authentication CRUD operations."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool

from agent_os.db.base import Base
from agent_os.auth import crud
from agent_os.auth.models import User, UserSettings
# Import all models to ensure relationships are resolved
from agent_os.knowledge.models import InboxItem, Card
from agent_os.tasks.models import Task


# Create async in-memory SQLite engine for testing
ASYNC_SQLITE_URL = "sqlite+aiosqlite:///:memory:"

async_engine = create_async_engine(
    ASYNC_SQLITE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture
async def db_session():
    """Create a test database session."""
    # Create only auth-related tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all, tables=[User.__table__, UserSettings.__table__])

    # Create session
    async_session_maker = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session


class TestCreateUser:
    """Test user creation."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, db_session: AsyncSession):
        """Test creating a new user."""
        user = await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password != "testpass123"  # Should be hashed
        assert user.id is not None

    @pytest.mark.asyncio
    async def test_create_user_creates_settings(self, db_session: AsyncSession):
        """Test creating user also creates default settings."""
        user = await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Refresh to load settings
        await db_session.refresh(user, ["settings"])

        assert user.settings is not None
        assert user.settings.daily_goal == 10
        assert user.settings.theme == "light"
        assert user.settings.language == "zh"


class TestGetUser:
    """Test user retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, db_session: AsyncSession):
        """Test getting user by ID."""
        # Create user first
        created_user = await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Get user by ID
        user = await crud.get_user_by_id(db_session, created_user.id)

        assert user is not None
        assert user.id == created_user.id
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, db_session: AsyncSession):
        """Test getting non-existent user by ID."""
        user = await crud.get_user_by_id(db_session, 999)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_username(self, db_session: AsyncSession):
        """Test getting user by username."""
        # Create user first
        await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Get user by username
        user = await crud.get_user_by_username(db_session, "testuser")

        assert user is not None
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, db_session: AsyncSession):
        """Test getting user by email."""
        # Create user first
        await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Get user by email
        user = await crud.get_user_by_email(db_session, "test@example.com")

        assert user is not None
        assert user.email == "test@example.com"


class TestAuthenticateUser:
    """Test user authentication."""

    @pytest.mark.asyncio
    async def test_authenticate_with_username(self, db_session: AsyncSession):
        """Test authentication with username."""
        # Create user first
        await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Authenticate
        user = await crud.authenticate_user(
            db=db_session,
            username="testuser",
            password="testpass123"
        )

        assert user is not None
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_authenticate_with_email(self, db_session: AsyncSession):
        """Test authentication with email."""
        # Create user first
        await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Authenticate with email
        user = await crud.authenticate_user(
            db=db_session,
            username="test@example.com",  # Using email as username
            password="testpass123"
        )

        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self, db_session: AsyncSession):
        """Test authentication with wrong password."""
        # Create user first
        await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Authenticate with wrong password
        user = await crud.authenticate_user(
            db=db_session,
            username="testuser",
            password="wrongpassword"
        )

        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_user(self, db_session: AsyncSession):
        """Test authentication with non-existent user."""
        user = await crud.authenticate_user(
            db=db_session,
            username="nonexistent",
            password="testpass123"
        )

        assert user is None


class TestUpdateUserSettings:
    """Test user settings update."""

    @pytest.mark.asyncio
    async def test_update_daily_goal(self, db_session: AsyncSession):
        """Test updating daily goal."""
        # Create user first
        user = await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Update settings
        settings = await crud.update_user_settings(
            db=db_session,
            user_id=user.id,
            daily_goal=20
        )

        assert settings is not None
        assert settings.daily_goal == 20
        assert settings.theme == "light"  # Unchanged

    @pytest.mark.asyncio
    async def test_update_theme(self, db_session: AsyncSession):
        """Test updating theme."""
        # Create user first
        user = await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Update settings
        settings = await crud.update_user_settings(
            db=db_session,
            user_id=user.id,
            theme="dark"
        )

        assert settings is not None
        assert settings.theme == "dark"

    @pytest.mark.asyncio
    async def test_update_multiple_settings(self, db_session: AsyncSession):
        """Test updating multiple settings at once."""
        # Create user first
        user = await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        # Update multiple settings
        settings = await crud.update_user_settings(
            db=db_session,
            user_id=user.id,
            daily_goal=15,
            theme="dark",
            language="en"
        )

        assert settings is not None
        assert settings.daily_goal == 15
        assert settings.theme == "dark"
        assert settings.language == "en"

    @pytest.mark.asyncio
    async def test_update_nonexistent_user_settings(self, db_session: AsyncSession):
        """Test updating settings for non-existent user."""
        settings = await crud.update_user_settings(
            db_session,
            user_id=999,
            daily_goal=20
        )

        assert settings is None
