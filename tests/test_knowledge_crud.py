"""Unit tests for Knowledge management CRUD operations (Inbox and Cards)."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_os.db.base import Base
from agent_os.auth.models import User, UserSettings
from agent_os.knowledge.models import InboxItem, Card
from agent_os.tasks.models import Task

from agent_os.knowledge import crud
from agent_os.knowledge.schema import (
    InboxItemCreate,
    InboxItemUpdate,
    CardCreate,
    CardUpdate,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
async def async_engine():
    """Create in-memory async SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(async_engine):
    """Create async database session for testing."""
    async_session_maker = sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_maker() as session:
        yield session


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password_here"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# =============================================================================
# Inbox Item CRUD Tests
# =============================================================================

class TestCreateInboxItem:
    """Test creating inbox items."""

    @pytest.mark.asyncio
    async def test_create_inbox_item_success(self, db_session: AsyncSession, test_user):
        """Test successful inbox item creation."""
        item_in = InboxItemCreate(content="Test content")
        created = await crud.create_inbox_item(
            db_session, user_id=test_user.id, obj_in=item_in
        )

        assert created.id is not None
        assert created.content == "Test content"
        assert created.user_id == test_user.id
        assert created.source == "manual"
        assert created.status == "raw"

    @pytest.mark.asyncio
    async def test_create_inbox_item_with_extra_data(self, db_session: AsyncSession, test_user):
        """Test creating inbox item with extra data."""
        extra_data = {"url": "https://example.com", "tags": ["test"]}
        item_in = InboxItemCreate(
            content="Test with extra data",
            source="api",
            extra_data=extra_data
        )
        created = await crud.create_inbox_item(
            db_session, user_id=test_user.id, obj_in=item_in
        )

        assert created.content == "Test with extra data"
        assert created.source == "api"
        assert created.extra_data == extra_data

    @pytest.mark.asyncio
    async def test_create_inbox_item_different_sources(self, db_session: AsyncSession, test_user):
        """Test creating inbox items from different sources."""
        sources = ["manual", "api", "import"]

        for source in sources:
            item_in = InboxItemCreate(content=f"From {source}", source=source)
            created = await crud.create_inbox_item(
                db_session, user_id=test_user.id, obj_in=item_in
            )
            assert created.source == source


class TestGetInboxItem:
    """Test getting inbox items."""

    @pytest.mark.asyncio
    async def test_get_inbox_item_by_id(self, db_session: AsyncSession, test_user):
        """Test getting inbox item by ID."""
        item_in = InboxItemCreate(content="Test content")
        created = await crud.create_inbox_item(
            db_session, user_id=test_user.id, obj_in=item_in
        )

        fetched = await crud.get_inbox_item(
            db_session, item_id=created.id, user_id=test_user.id
        )

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.content == "Test content"

    @pytest.mark.asyncio
    async def test_get_inbox_item_not_found(self, db_session: AsyncSession, test_user):
        """Test getting non-existent inbox item."""
        fetched = await crud.get_inbox_item(
            db_session, item_id=999, user_id=test_user.id
        )
        assert fetched is None

    @pytest.mark.asyncio
    async def test_get_inbox_item_wrong_user(self, db_session: AsyncSession):
        """Test getting inbox item from different user."""
        # Create two users
        user1 = User(username="user1", email="user1@example.com", hashed_password="hash")
        user2 = User(username="user2", email="user2@example.com", hashed_password="hash")
        db_session.add_all([user1, user2])
        await db_session.commit()

        # Create item for user1
        item_in = InboxItemCreate(content="User1 content")
        created = await crud.create_inbox_item(
            db_session, user_id=user1.id, obj_in=item_in
        )

        # Try to get as user2
        fetched = await crud.get_inbox_item(
            db_session, item_id=created.id, user_id=user2.id
        )
        assert fetched is None


class TestListInboxItems:
    """Test listing inbox items."""

    @pytest.mark.asyncio
    async def test_list_inbox_items_empty(self, db_session: AsyncSession, test_user):
        """Test listing with no items."""
        items, total = await crud.get_inbox_items(db_session, user_id=test_user.id)
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_inbox_items_multiple(self, db_session: AsyncSession, test_user):
        """Test listing multiple items."""
        # Create 5 items
        for i in range(5):
            item_in = InboxItemCreate(content=f"Content {i}")
            await crud.create_inbox_item(
                db_session, user_id=test_user.id, obj_in=item_in
            )

        items, total = await crud.get_inbox_items(db_session, user_id=test_user.id)
        assert len(items) == 5
        assert total == 5

    @pytest.mark.asyncio
    async def test_list_inbox_items_with_status_filter(self, db_session: AsyncSession, test_user):
        """Test listing with status filter."""
        # Create items with different statuses
        item1 = InboxItemCreate(content="Raw item")
        item2 = InboxItemCreate(content="Processed item")
        created1 = await crud.create_inbox_item(
            db_session, user_id=test_user.id, obj_in=item1
        )
        created2 = await crud.create_inbox_item(
            db_session, user_id=test_user.id, obj_in=item2
        )

        # Update status
        await crud.update_inbox_item_status(
            db_session, item_id=created2.id, user_id=test_user.id, status="processed"
        )

        # Filter by status
        raw_items, raw_total = await crud.get_inbox_items(
            db_session, user_id=test_user.id, status="raw"
        )
        assert len(raw_items) == 1
        assert raw_total == 1

    @pytest.mark.asyncio
    async def test_list_inbox_items_with_source_filter(self, db_session: AsyncSession, test_user):
        """Test listing with source filter."""
        # Create items from different sources
        await crud.create_inbox_item(
            db_session,
            user_id=test_user.id,
            obj_in=InboxItemCreate(content="Manual", source="manual")
        )
        await crud.create_inbox_item(
            db_session,
            user_id=test_user.id,
            obj_in=InboxItemCreate(content="API", source="api")
        )

        # Filter by source
        manual_items, manual_total = await crud.get_inbox_items(
            db_session, user_id=test_user.id, source="manual"
        )
        api_items, api_total = await crud.get_inbox_items(
            db_session, user_id=test_user.id, source="api"
        )

        assert len(manual_items) == 1
        assert manual_total == 1
        assert len(api_items) == 1
        assert api_total == 1

    @pytest.mark.asyncio
    async def test_list_inbox_items_pagination(self, db_session: AsyncSession, test_user):
        """Test pagination."""
        # Create 15 items
        for i in range(15):
            await crud.create_inbox_item(
                db_session,
                user_id=test_user.id,
                obj_in=InboxItemCreate(content=f"Content {i}")
            )

        # Get first page
        items1, total = await crud.get_inbox_items(
            db_session, user_id=test_user.id, skip=0, limit=10
        )
        assert len(items1) == 10
        assert total == 15

        # Get second page
        items2, total = await crud.get_inbox_items(
            db_session, user_id=test_user.id, skip=10, limit=10
        )
        assert len(items2) == 5


class TestUpdateInboxItem:
    """Test updating inbox items."""

    @pytest.mark.asyncio
    async def test_update_inbox_item_content(self, db_session: AsyncSession, test_user):
        """Test updating inbox item content."""
        created = await crud.create_inbox_item(
            db_session,
            user_id=test_user.id,
            obj_in=InboxItemCreate(content="Original")
        )

        updated = await crud.update_inbox_item(
            db_session,
            db_obj=created,
            obj_in=InboxItemUpdate(content="Updated")
        )

        assert updated.content == "Updated"

    @pytest.mark.asyncio
    async def test_update_inbox_item_status(self, db_session: AsyncSession, test_user):
        """Test updating inbox item status."""
        created = await crud.create_inbox_item(
            db_session,
            user_id=test_user.id,
            obj_in=InboxItemCreate(content="Test")
        )

        updated = await crud.update_inbox_item_status(
            db_session, item_id=created.id, user_id=test_user.id, status="processed"
        )

        assert updated.status == "processed"

    @pytest.mark.asyncio
    async def test_update_inbox_item_with_dict(self, db_session: AsyncSession, test_user):
        """Test updating inbox item with dict."""
        created = await crud.create_inbox_item(
            db_session,
            user_id=test_user.id,
            obj_in=InboxItemCreate(content="Test")
        )

        updated = await crud.update_inbox_item(
            db_session,
            db_obj=created,
            obj_in={"content": "Updated content"}
        )

        assert updated.content == "Updated content"


class TestDeleteInboxItem:
    """Test deleting inbox items."""

    @pytest.mark.asyncio
    async def test_delete_inbox_item_success(self, db_session: AsyncSession, test_user):
        """Test successful deletion."""
        created = await crud.create_inbox_item(
            db_session,
            user_id=test_user.id,
            obj_in=InboxItemCreate(content="To be deleted")
        )

        deleted = await crud.delete_inbox_item(
            db_session, item_id=created.id, user_id=test_user.id
        )

        assert deleted is True

        # Verify item is gone
        fetched = await crud.get_inbox_item(
            db_session, item_id=created.id, user_id=test_user.id
        )
        assert fetched is None

    @pytest.mark.asyncio
    async def test_delete_inbox_item_not_found(self, db_session: AsyncSession, test_user):
        """Test deleting non-existent item."""
        deleted = await crud.delete_inbox_item(
            db_session, item_id=999, user_id=test_user.id
        )
        assert deleted is False


# =============================================================================
# Card CRUD Tests
# =============================================================================

class TestCreateCard:
    """Test creating cards."""

    @pytest.mark.asyncio
    async def test_create_card_success(self, db_session: AsyncSession, test_user):
        """Test successful card creation."""
        card_in = CardCreate(
            title="Test Card",
            content="Test content",
            para_type="concept"
        )
        created = await crud.create_card(
            db_session, user_id=test_user.id, obj_in=card_in
        )

        assert created.id is not None
        assert created.title == "Test Card"
        assert created.content == "Test content"
        assert created.para_type == "concept"

    @pytest.mark.asyncio
    async def test_create_card_with_source(self, db_session: AsyncSession, test_user):
        """Test creating card from inbox item."""
        # Create inbox item first
        inbox = await crud.create_inbox_item(
            db_session,
            user_id=test_user.id,
            obj_in=InboxItemCreate(content="Source content")
        )

        card_in = CardCreate(
            title="Card from inbox",
            content="Card content",
            para_type="concept",
            source_inbox_item_id=inbox.id
        )
        created = await crud.create_card(
            db_session, user_id=test_user.id, obj_in=card_in
        )

        assert created.source_inbox_item_id == inbox.id


class TestGetCard:
    """Test getting cards."""

    @pytest.mark.asyncio
    async def test_get_card_by_id(self, db_session: AsyncSession, test_user):
        """Test getting card by ID."""
        card_in = CardCreate(
            title="Test Card",
            content="Test content",
            para_type="concept"
        )
        created = await crud.create_card(
            db_session, user_id=test_user.id, obj_in=card_in
        )

        fetched = await crud.get_card(
            db_session, card_id=created.id, user_id=test_user.id
        )

        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.title == "Test Card"

    @pytest.mark.asyncio
    async def test_get_card_not_found(self, db_session: AsyncSession, test_user):
        """Test getting non-existent card."""
        fetched = await crud.get_card(
            db_session, card_id=999, user_id=test_user.id
        )
        assert fetched is None


class TestListCards:
    """Test listing cards."""

    @pytest.mark.asyncio
    async def test_list_cards_empty(self, db_session: AsyncSession, test_user):
        """Test listing with no cards."""
        cards, total = await crud.get_cards(db_session, user_id=test_user.id)
        assert cards == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_cards_multiple(self, db_session: AsyncSession, test_user):
        """Test listing multiple cards."""
        # Create 5 cards
        for i in range(5):
            await crud.create_card(
                db_session,
                user_id=test_user.id,
                obj_in=CardCreate(
                    title=f"Card {i}",
                    content=f"Content {i}",
                    para_type="concept"
                )
            )

        cards, total = await crud.get_cards(db_session, user_id=test_user.id)
        assert len(cards) == 5
        assert total == 5

    @pytest.mark.asyncio
    async def test_list_cards_by_para_type(self, db_session: AsyncSession, test_user):
        """Test filtering by para_type."""
        # Create cards with different types
        await crud.create_card(
            db_session,
            user_id=test_user.id,
            obj_in=CardCreate(title="C1", content="Content", para_type="concept")
        )
        await crud.create_card(
            db_session,
            user_id=test_user.id,
            obj_in=CardCreate(title="A1", content="Content", para_type="action")
        )
        await crud.create_card(
            db_session,
            user_id=test_user.id,
            obj_in=CardCreate(title="R1", content="Content", para_type="reference")
        )

        # Filter by type
        concept_cards, concept_total = await crud.get_cards(
            db_session, user_id=test_user.id, para_type="concept"
        )
        action_cards, action_total = await crud.get_cards(
            db_session, user_id=test_user.id, para_type="action"
        )

        assert len(concept_cards) == 1
        assert concept_total == 1
        assert len(action_cards) == 1
        assert action_total == 1

    @pytest.mark.asyncio
    async def test_list_cards_by_tags(self, db_session: AsyncSession, test_user):
        """Test filtering by tags."""
        # Create cards with tags
        await crud.create_card(
            db_session,
            user_id=test_user.id,
            obj_in=CardCreate(
                title="Python Card",
                content="Python content",
                para_type="concept",
                tags=["python", "programming"]
            )
        )
        await crud.create_card(
            db_session,
            user_id=test_user.id,
            obj_in=CardCreate(
                title="JS Card",
                content="JS content",
                para_type="concept",
                tags=["javascript", "programming"]
            )
        )

        # Filter by tag
        python_cards, python_total = await crud.get_cards(
            db_session, user_id=test_user.id, tags=["python"]
        )
        assert len(python_cards) == 1
        assert python_total == 1
        assert python_cards[0].title == "Python Card"


class TestUpdateCard:
    """Test updating cards."""

    @pytest.mark.asyncio
    async def test_update_card(self, db_session: AsyncSession, test_user):
        """Test updating card."""
        created = await crud.create_card(
            db_session,
            user_id=test_user.id,
            obj_in=CardCreate(
                title="Original",
                content="Original content",
                para_type="concept"
            )
        )

        updated = await crud.update_card(
            db_session,
            db_obj=created,
            obj_in=CardCreate(
                title="Updated",
                content="Updated content",
                para_type="action"
            )
        )

        assert updated.title == "Updated"
        assert updated.content == "Updated content"
        assert updated.para_type == "action"


class TestDeleteCard:
    """Test deleting cards."""

    @pytest.mark.asyncio
    async def test_delete_card_success(self, db_session: AsyncSession, test_user):
        """Test successful deletion."""
        created = await crud.create_card(
            db_session,
            user_id=test_user.id,
            obj_in=CardCreate(
                title="To delete",
                content="Content",
                para_type="concept"
            )
        )

        deleted = await crud.delete_card(
            db_session, card_id=created.id, user_id=test_user.id
        )

        assert deleted is True

        # Verify card is gone
        fetched = await crud.get_card(
            db_session, card_id=created.id, user_id=test_user.id
        )
        assert fetched is None
