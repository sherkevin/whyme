"""API integration tests for Knowledge management endpoints."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tests.test_app import test_app as app

from agent_os.auth.jwt_handler import create_access_token
from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash
from agent_os.db.base import Base
from agent_os.db.session import get_db
from agent_os.knowledge.models import Card, InboxItem

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


@pytest.fixture
async def test_user(db_session):
    """Create and authenticate test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass123")
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_headers(test_user):
    """Get authentication headers for test user."""
    token = create_access_token(user_id=test_user.id)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Inbox API Tests
# =============================================================================

class TestInboxAPI:
    """Test Inbox API endpoints."""

    def test_create_inbox_item(self, test_client, auth_headers):
        """Test creating a new inbox item."""
        response = test_client.post(
            "/api/v1/knowledge/inbox",
            json={
                "content": "Test inbox item",
                "source": "manual",
                "extra_data": {"key": "value"}
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Test inbox item"
        assert data["source"] == "manual"
        assert data["status"] == "raw"
        assert "id" in data
        assert "created_at" in data

    def test_create_inbox_item_invalid_source(self, test_client, auth_headers):
        """Test creating inbox item with invalid source."""
        response = test_client.post(
            "/api/v1/knowledge/inbox",
            json={
                "content": "Test",
                "source": "invalid_source"
            },
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    async def test_get_inbox_item(self, test_client, db_session, test_user, auth_headers):
        """Test getting a specific inbox item."""
        # Create an item first
        item = InboxItem(
            user_id=test_user.id,
            content="Test content",
            source="manual"
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        # Get the item
        response = test_client.get(
            f"/api/v1/knowledge/inbox/{item.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == item.id
        assert data["content"] == "Test content"

    def test_get_inbox_item_not_found(self, test_client, auth_headers):
        """Test getting non-existent inbox item."""
        response = test_client.get(
            "/api/v1/knowledge/inbox/999",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_list_inbox_items_empty(self, test_client, auth_headers):
        """Test listing inbox items when empty."""
        response = test_client.get(
            "/api/v1/knowledge/inbox",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_inbox_items_with_data(self, test_client, db_session, test_user, auth_headers):
        """Test listing inbox items with data."""
        # Create multiple items
        for i in range(3):
            item = InboxItem(
                user_id=test_user.id,
                content=f"Content {i}",
                source="manual"
            )
            db_session.add(item)
        await db_session.commit()

        # List items
        response = test_client.get(
            "/api/v1/knowledge/inbox",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_list_inbox_items_with_status_filter(self, test_client, db_session, test_user, auth_headers):
        """Test listing inbox items with status filter."""
        # Create items with different statuses
        item1 = InboxItem(user_id=test_user.id, content="Raw", status="raw")
        item2 = InboxItem(user_id=test_user.id, content="Processed", status="processed")
        db_session.add_all([item1, item2])
        await db_session.commit()

        # Filter by status
        response = test_client.get(
            "/api/v1/knowledge/inbox?status=raw",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["content"] == "Raw"

    async def test_list_inbox_items_pagination(self, test_client, db_session, test_user, auth_headers):
        """Test pagination for inbox items."""
        # Create 5 items
        for i in range(5):
            item = InboxItem(user_id=test_user.id, content=f"Item {i}")
            db_session.add(item)
        await db_session.commit()

        # Get first page
        response = test_client.get(
            "/api/v1/knowledge/inbox?page=1&page_size=3",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 3
        assert data["page"] == 1

    async def test_update_inbox_item(self, test_client, db_session, test_user, auth_headers):
        """Test updating an inbox item."""
        item = InboxItem(user_id=test_user.id, content="Original")
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        response = test_client.put(
            f"/api/v1/knowledge/inbox/{item.id}",
            json={"content": "Updated"},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated"

    async def test_update_inbox_item_status(self, test_client, db_session, test_user, auth_headers):
        """Test updating inbox item status via PATCH."""
        item = InboxItem(user_id=test_user.id, content="Test", status="raw")
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        response = test_client.patch(
            f"/api/v1/knowledge/inbox/{item.id}/status?new_status=processed",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"

    async def test_update_inbox_item_invalid_status(self, test_client, db_session, test_user, auth_headers):
        """Test updating with invalid status."""
        item = InboxItem(user_id=test_user.id, content="Test")
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        response = test_client.patch(
            f"/api/v1/knowledge/inbox/{item.id}/status?new_status=invalid",
            headers=auth_headers
        )

        assert response.status_code == 400

    async def test_delete_inbox_item(self, test_client, db_session, test_user, auth_headers):
        """Test deleting an inbox item."""
        item = InboxItem(user_id=test_user.id, content="To be deleted")
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        response = test_client.delete(
            f"/api/v1/knowledge/inbox/{item.id}",
            headers=auth_headers
        )

        assert response.status_code == 204

        # Verify deletion
        get_response = test_client.get(
            f"/api/v1/knowledge/inbox/{item.id}",
            headers=auth_headers
        )
        assert get_response.status_code == 404

    def test_unauthorized_access(self, test_client):
        """Test accessing API without authentication."""
        response = test_client.get("/api/v1/knowledge/inbox")
        assert response.status_code == 401


# =============================================================================
# Card API Tests
# =============================================================================

class TestCardAPI:
    """Test Card API endpoints."""

    def test_create_card(self, test_client, auth_headers):
        """Test creating a new card."""
        response = test_client.post(
            "/api/v1/knowledge/cards",
            json={
                "title": "Test Card",
                "content": "Card content",
                "para_type": "concept",
                "tags": ["python", "fastapi"]
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Test Card"
        assert data["para_type"] == "concept"
        assert data["tags"] == ["python", "fastapi"]
        assert "id" in data

    async def test_create_card_with_inbox_source(self, test_client, db_session, test_user, auth_headers):
        """Test creating card linked to inbox item."""
        # Create inbox item first
        inbox = InboxItem(user_id=test_user.id, content="Source content")
        db_session.add(inbox)
        await db_session.commit()
        await db_session.refresh(inbox)

        # Create card with source
        response = test_client.post(
            "/api/v1/knowledge/cards",
            json={
                "title": "Card from inbox",
                "content": "Card content",
                "para_type": "action",
                "source_inbox_item_id": inbox.id
            },
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["source_inbox_item_id"] == inbox.id

    def test_create_card_invalid_para_type(self, test_client, auth_headers):
        """Test creating card with invalid para_type."""
        response = test_client.post(
            "/api/v1/knowledge/cards",
            json={
                "title": "Test",
                "content": "Content",
                "para_type": "invalid"
            },
            headers=auth_headers
        )

        assert response.status_code == 422

    async def test_get_card(self, test_client, db_session, test_user, auth_headers):
        """Test getting a specific card."""
        card = Card(
            user_id=test_user.id,
            title="Test Card",
            content="Content",
            para_type="concept"
        )
        db_session.add(card)
        await db_session.commit()
        await db_session.refresh(card)

        response = test_client.get(
            f"/api/v1/knowledge/cards/{card.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == card.id
        assert data["title"] == "Test Card"

    def test_get_card_not_found(self, test_client, auth_headers):
        """Test getting non-existent card."""
        response = test_client.get(
            "/api/v1/knowledge/cards/999",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_list_cards_empty(self, test_client, auth_headers):
        """Test listing cards when empty."""
        response = test_client.get(
            "/api/v1/knowledge/cards",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    async def test_list_cards_with_para_type_filter(self, test_client, db_session, test_user, auth_headers):
        """Test listing cards with para_type filter."""
        # Create cards with different types
        card1 = Card(user_id=test_user.id, title="C1", content="Content", para_type="concept")
        card2 = Card(user_id=test_user.id, title="A1", content="Content", para_type="action")
        db_session.add_all([card1, card2])
        await db_session.commit()

        # Filter by para_type
        response = test_client.get(
            "/api/v1/knowledge/cards?para_type=concept",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["para_type"] == "concept"

    async def test_list_cards_with_tags_filter(self, test_client, db_session, test_user, auth_headers):
        """Test listing cards with tags filter."""
        # Create cards with tags
        card1 = Card(user_id=test_user.id, title="Python", content="Content", para_type="concept", tags=["python", "fastapi"])
        card2 = Card(user_id=test_user.id, title="JavaScript", content="Content", para_type="concept", tags=["javascript"])
        db_session.add_all([card1, card2])
        await db_session.commit()

        # Filter by tags (comma-separated)
        response = test_client.get(
            "/api/v1/knowledge/cards?tags=python",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Python"

    async def test_update_card(self, test_client, db_session, test_user, auth_headers):
        """Test updating a card."""
        card = Card(user_id=test_user.id, title="Original", content="Content", para_type="concept")
        db_session.add(card)
        await db_session.commit()
        await db_session.refresh(card)

        response = test_client.put(
            f"/api/v1/knowledge/cards/{card.id}",
            json={"title": "Updated", "tags": ["new_tag"]},
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
        assert "new_tag" in data["tags"]

    async def test_delete_card(self, test_client, db_session, test_user, auth_headers):
        """Test deleting a card."""
        card = Card(user_id=test_user.id, title="Delete me", content="Content", para_type="concept")
        db_session.add(card)
        await db_session.commit()
        await db_session.refresh(card)

        response = test_client.delete(
            f"/api/v1/knowledge/cards/{card.id}",
            headers=auth_headers
        )

        assert response.status_code == 204


# =============================================================================
# Vector Search API Tests
# =============================================================================

class TestVectorSearchAPI:
    """Test Vector Search API endpoints."""

    def test_vector_search_cards(self, test_client, auth_headers):
        """Test vector search endpoint."""
        response = test_client.post(
            "/api/v1/knowledge/cards/search",
            json={
                "query": "python programming",
                "limit": 5
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert "total" in data
        assert data["query"] == "python programming"

    def test_vector_search_with_filters(self, test_client, auth_headers):
        """Test vector search with para_type filter."""
        response = test_client.post(
            "/api/v1/knowledge/cards/search",
            json={
                "query": "test query",
                "limit": 10,
                "para_type": "concept"
            },
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["results"], list)

    def test_vector_search_invalid_query(self, test_client, auth_headers):
        """Test vector search with empty query."""
        response = test_client.post(
            "/api/v1/knowledge/cards/search",
            json={
                "query": "",
                "limit": 10
            },
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_vector_search_limit_bounds(self, test_client, auth_headers):
        """Test vector search limit validation."""
        # Test limit too low
        response = test_client.post(
            "/api/v1/knowledge/cards/search",
            json={"query": "test", "limit": 0},
            headers=auth_headers
        )
        assert response.status_code == 422

        # Test limit too high
        response = test_client.post(
            "/api/v1/knowledge/cards/search",
            json={"query": "test", "limit": 100},
            headers=auth_headers
        )
        assert response.status_code == 422

    async def test_find_similar_cards(self, test_client, db_session, test_user, auth_headers):
        """Test finding similar cards endpoint."""
        # Create a reference card
        card = Card(
            user_id=test_user.id,
            title="Python FastAPI",
            content="Building APIs with FastAPI framework",
            para_type="concept"
        )
        db_session.add(card)
        await db_session.commit()
        await db_session.refresh(card)

        # Find similar cards
        response = test_client.get(
            f"/api/v1/knowledge/cards/{card.id}/similar?limit=5",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "total" in data

    def test_find_similar_cards_not_found(self, test_client, auth_headers):
        """Test finding similar cards for non-existent card."""
        response = test_client.get(
            "/api/v1/knowledge/cards/999/similar",
            headers=auth_headers
        )

        assert response.status_code == 404
