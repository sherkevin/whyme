"""Unit tests for Knowledge management schemas (Inbox and Cards)."""

import pytest
from datetime import datetime
from agent_os.knowledge.schema import (
    InboxItemCreate,
    InboxItemUpdate,
    InboxItemResponse,
    InboxItemList,
    CardCreate,
    CardUpdate,
    CardResponse,
    CardList,
    SearchResultItem,
    SearchResponse,
    KnowledgeContextResponse,
)


# =============================================================================
# Inbox Schema Tests
# =============================================================================

class TestInboxItemCreate:
    """Test InboxItemCreate schema."""

    def test_valid_inbox_item_create(self):
        """Test creating valid inbox item."""
        data = {
            "content": "Test content",
            "source": "manual",
            "extra_data": {"key": "value"}
        }
        item = InboxItemCreate(**data)
        assert item.content == "Test content"
        assert item.source == "manual"
        assert item.extra_data == {"key": "value"}

    def test_inbox_item_create_defaults(self):
        """Test default values."""
        item = InboxItemCreate(content="Test")
        assert item.source == "manual"
        assert item.extra_data == {}

    def test_inbox_item_create_content_too_short(self):
        """Test content too short."""
        with pytest.raises(ValueError):
            InboxItemCreate(content="")

    def test_inbox_item_create_content_too_long(self):
        """Test content too long."""
        with pytest.raises(ValueError):
            InboxItemCreate(content="x" * 10001)

    def test_inbox_item_create_invalid_source(self):
        """Test invalid source."""
        with pytest.raises(ValueError):
            InboxItemCreate(content="Test", source="invalid")


class TestInboxItemUpdate:
    """Test InboxItemUpdate schema."""

    def test_valid_inbox_item_update(self):
        """Test valid update."""
        update = InboxItemUpdate(content="Updated content")
        assert update.content == "Updated content"

    def test_inbox_item_update_partial(self):
        """Test partial update."""
        update = InboxItemUpdate(status="processed")
        assert update.status == "processed"
        assert update.content is None

    def test_inbox_item_update_invalid_status(self):
        """Test invalid status."""
        with pytest.raises(ValueError):
            InboxItemUpdate(status="invalid")


class TestInboxItemResponse:
    """Test InboxItemResponse schema."""

    def test_inbox_item_response_from_attributes(self):
        """Test creating response from attributes."""
        # Mock object with required attributes
        class MockInboxItem:
            id = 1
            user_id = 1
            content = "Test content"
            status = "raw"
            source = "manual"
            extra_data = {}
            created_at = datetime.now()
            updated_at = datetime.now()

        mock_item = MockInboxItem()
        response = InboxItemResponse.model_validate(mock_item)
        assert response.id == 1
        assert response.content == "Test content"
        assert response.status == "raw"


class TestInboxItemList:
    """Test InboxItemList schema."""

    def test_valid_inbox_item_list(self):
        """Test valid item list."""
        items = [
            InboxItemResponse(
                id=1,
                user_id=1,
                content="Test 1",
                status="raw",
                source="manual",
                extra_data={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        ]
        item_list = InboxItemList(items=items, total=1, page=1, page_size=20)
        assert len(item_list.items) == 1
        assert item_list.total == 1
        assert item_list.page == 1
        assert item_list.page_size == 20

    def test_inbox_item_list_defaults(self):
        """Test default values."""
        item_list = InboxItemList(items=[], total=0)
        assert item_list.page == 1
        assert item_list.page_size == 20


# =============================================================================
# Card Schema Tests
# =============================================================================

class TestCardCreate:
    """Test CardCreate schema."""

    def test_valid_card_create(self):
        """Test creating valid card."""
        data = {
            "title": "Test Card",
            "content": "Card content",
            "para_type": "concept",
            "tags": ["tag1", "tag2"],
            "source_inbox_item_id": 1
        }
        card = CardCreate(**data)
        assert card.title == "Test Card"
        assert card.para_type == "concept"
        assert card.tags == ["tag1", "tag2"]

    def test_card_create_defaults(self):
        """Test default values."""
        card = CardCreate(
            title="Test",
            content="Content",
            para_type="action"
        )
        assert card.tags == []
        assert card.source_inbox_item_id is None

    def test_card_create_title_too_short(self):
        """Test title too short."""
        with pytest.raises(ValueError):
            CardCreate(title="", content="Content", para_type="concept")

    def test_card_create_title_too_long(self):
        """Test title too long."""
        with pytest.raises(ValueError):
            CardCreate(
                title="x" * 201,
                content="Content",
                para_type="concept"
            )

    def test_card_create_invalid_para_type(self):
        """Test invalid para_type."""
        with pytest.raises(ValueError):
            CardCreate(
                title="Test",
                content="Content",
                para_type="invalid"
            )


class TestCardUpdate:
    """Test CardUpdate schema."""

    def test_valid_card_update(self):
        """Test valid update."""
        update = CardUpdate(title="Updated title")
        assert update.title == "Updated title"

    def test_card_update_partial(self):
        """Test partial update."""
        update = CardUpdate(tags=["new_tag"])
        assert update.tags == ["new_tag"]
        assert update.title is None

    def test_card_update_invalid_para_type(self):
        """Test invalid para_type."""
        with pytest.raises(ValueError):
            CardUpdate(para_type="invalid")


class TestCardResponse:
    """Test CardResponse schema."""

    def test_card_response_from_attributes(self):
        """Test creating response from attributes."""
        class MockCard:
            id = 1
            user_id = 1
            title = "Test Card"
            content = "Card content"
            para_type = "concept"
            tags = ["tag1"]
            source_inbox_item_id = None
            created_at = datetime.now()
            updated_at = datetime.now()

        mock_card = MockCard()
        response = CardResponse.model_validate(mock_card)
        assert response.id == 1
        assert response.title == "Test Card"
        assert response.para_type == "concept"


class TestCardList:
    """Test CardList schema."""

    def test_valid_card_list(self):
        """Test valid card list."""
        cards = [
            CardResponse(
                id=1,
                user_id=1,
                title="Test",
                content="Content",
                para_type="concept",
                tags=[],
                source_inbox_item_id=None,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        ]
        card_list = CardList(items=cards, total=1, page=1, page_size=20)
        assert len(card_list.items) == 1
        assert card_list.total == 1


# =============================================================================
# Search Schema Tests
# =============================================================================

class TestSearchResultItem:
    """Test SearchResultItem schema."""

    def test_valid_search_result(self):
        """Test valid search result."""
        result = SearchResultItem(
            card_id=1,
            title="Test",
            content="Content",
            para_type="concept",
            similarity=0.95
        )
        assert result.card_id == 1
        assert result.similarity == 0.95

    def test_search_result_similarity_bounds(self):
        """Test similarity score bounds."""
        # Valid range
        SearchResultItem(
            card_id=1,
            title="Test",
            content="Content",
            para_type="concept",
            similarity=0.0
        )
        SearchResultItem(
            card_id=1,
            title="Test",
            content="Content",
            para_type="concept",
            similarity=1.0
        )

    def test_search_result_similarity_too_low(self):
        """Test similarity too low."""
        with pytest.raises(ValueError):
            SearchResultItem(
                card_id=1,
                title="Test",
                content="Content",
                para_type="concept",
                similarity=-0.1
            )

    def test_search_result_similarity_too_high(self):
        """Test similarity too high."""
        with pytest.raises(ValueError):
            SearchResultItem(
                card_id=1,
                title="Test",
                content="Content",
                para_type="concept",
                similarity=1.1
            )


class TestSearchResponse:
    """Test SearchResponse schema."""

    def test_valid_search_response(self):
        """Test valid search response."""
        results = [
            SearchResultItem(
                card_id=1,
                title="Test",
                content="Content",
                para_type="concept",
                similarity=0.95
            )
        ]
        response = SearchResponse(
            query="test query",
            results=results,
            total=1
        )
        assert response.query == "test query"
        assert len(response.results) == 1
        assert response.total == 1


class TestKnowledgeContextResponse:
    """Test KnowledgeContextResponse schema."""

    def test_valid_context_response(self):
        """Test valid context response."""
        results = [
            SearchResultItem(
                card_id=1,
                title="Test",
                content="Content",
                para_type="concept",
                similarity=0.95
            )
        ]
        response = KnowledgeContextResponse(
            task_description="Test task",
            context_cards=results,
            total_cards=1,
            formatted_context="Context text"
        )
        assert response.task_description == "Test task"
        assert response.total_cards == 1
        assert response.formatted_context == "Context text"
