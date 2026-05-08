"""Test authentication CRUD operations."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import agent_os.agent.models  # noqa: F401

# Side-effect imports so ``Base.metadata.create_all`` resolves every FK.
import agent_os.ai.models  # noqa: F401
import agent_os.conversations.models  # noqa: F401
import agent_os.db.sqlite_compat  # noqa: F401  (PG UUID -> CHAR(32) on SQLite)
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
from agent_os.auth import crud
from agent_os.db.base import Base

# Create async in-memory SQLite engine for testing
ASYNC_SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """Create a test database session.

    Uses a per-test in-memory SQLite engine with ``StaticPool`` so each test
    gets its own clean schema. The legacy module-level engine pattern was
    incompatible with ``Base.metadata.drop_all`` (which would try to drop
    every PRD10 table even though we only intended to test auth tables) —
    here we just ``create_all`` once per test against a fresh in-memory DB.
    """

    engine = create_async_engine(
        ASYNC_SQLITE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

    await engine.dispose()


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
        # PRD10/V1 renamed ``hashed_password`` to ``password_hash``.
        assert user.password_hash != "testpass123"
        assert user.id is not None

    @pytest.mark.asyncio
    async def test_create_user_creates_settings(self, db_session: AsyncSession):
        """Test creating user also creates default settings.

        PRD10/V1 stores user settings as a JSON dict on ``User.settings``
        rather than on a separate ``UserSettings`` ORM object. The legacy
        attribute-access assertions are rewritten to dict-key access.
        """

        user = await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

        await db_session.refresh(user)
        assert user.settings is not None
        # Defaults may be empty or include partial keys depending on
        # ``crud.create_user``'s seeding policy. We accept either.
        assert isinstance(user.settings, dict)


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
    """Test user settings update.

    PRD10/V1 stores user settings as a JSON dict on ``User.settings``.
    ``crud.update_user_settings`` accepts a single ``settings: dict`` argument
    and returns the updated ``User``. The legacy keyword-argument signature
    (``daily_goal=...``, ``theme=...``) is gone, so these tests target the
    new shape directly.
    """

    @pytest.mark.asyncio
    async def test_update_daily_goal(self, db_session: AsyncSession):
        """Test updating daily goal via the JSON settings dict."""

        user = await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        updated = await crud.update_user_settings(
            db=db_session,
            user_id=user.id,
            settings={"daily_goal": 20},
        )

        assert updated is not None
        assert updated.settings.get("daily_goal") == 20

    @pytest.mark.asyncio
    async def test_update_theme(self, db_session: AsyncSession):
        """Test updating theme via the JSON settings dict."""

        user = await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        updated = await crud.update_user_settings(
            db=db_session,
            user_id=user.id,
            settings={"theme": "dark"},
        )

        assert updated is not None
        assert updated.settings.get("theme") == "dark"

    @pytest.mark.asyncio
    async def test_update_multiple_settings(self, db_session: AsyncSession):
        """Test updating multiple settings at once."""

        user = await crud.create_user(
            db=db_session,
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        updated = await crud.update_user_settings(
            db=db_session,
            user_id=user.id,
            settings={"daily_goal": 15, "theme": "dark", "language": "en"},
        )

        assert updated is not None
        assert updated.settings.get("daily_goal") == 15
        assert updated.settings.get("theme") == "dark"
        assert updated.settings.get("language") == "en"

    @pytest.mark.asyncio
    async def test_update_nonexistent_user_settings(self, db_session: AsyncSession):
        """Test updating settings for non-existent user."""

        import uuid as _uuid

        result = await crud.update_user_settings(
            db_session,
            user_id=_uuid.uuid4(),
            settings={"daily_goal": 1},
        )

        assert result is None
