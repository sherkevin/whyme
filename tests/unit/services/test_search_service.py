"""Unit tests for Stage 4 SearchService and SearchEngine."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from agent_os.search_engine.search_service import SearchService
from agent_os.search_engine.search_engine import SearchEngine, SearchQuery, SearchResult
from agent_os.search_engine.models import SearchIndex


@pytest.mark.asyncio
class TestSearchService:
    """Test SearchService functionality."""

    async def test_index_item_create(self, db_session):
        """Test creating a new search index."""
        service = SearchService(db_session)
        item_id = uuid.uuid4()

        index = await service.index_item(
            item_type="card",
            item_id=str(item_id),
            title="Test Card",
            content="This is test content for searching",
            tags=["test", "example"],
            search_metadata={"workspace_id": str(uuid.uuid4())}
        )

        assert index.id is not None
        assert index.item_type == "card"
        assert index.item_id == item_id
        assert index.title == "Test Card"
        assert len(index.tags) == 2
        print(f"✅ Created search index: {index.item_type}:{index.item_id}")

    async def test_index_item_update(self, db_session):
        """Test updating an existing search index."""
        service = SearchService(db_session)
        item_id = uuid.uuid4()

        # Create initial index
        await service.index_item(
            item_type="task",
            item_id=str(item_id),
            title="Original Title",
            content="Original content"
        )

        # Update the index
        updated_index = await service.index_item(
            item_type="task",
            item_id=str(item_id),
            title="Updated Title",
            content="Updated content",
            tags=["updated"]
        )

        assert updated_index.title == "Updated Title"
        assert updated_index.content == "Updated content"
        assert "updated" in updated_index.tags
        print(f"✅ Updated search index: {updated_index.item_type}:{updated_index.item_id}")

    async def test_get_index(self, db_session):
        """Test retrieving a search index."""
        service = SearchService(db_session)
        item_id = uuid.uuid4()

        # Create index
        await service.index_item(
            item_type="note",
            item_id=str(item_id),
            title="Test Note"
        )

        # Get index
        index = await service.get_index("note", str(item_id))

        assert index is not None
        assert index.item_type == "note"
        assert index.item_id == item_id
        print(f"✅ Retrieved search index: {index.item_type}:{index.item_id}")

    async def test_get_index_not_found(self, db_session):
        """Test getting a non-existent index."""
        service = SearchService(db_session)

        index = await service.get_index("card", str(uuid.uuid4()))

        assert index is None
        print("✅ get_index returns None for non-existent index")

    async def test_delete_index(self, db_session):
        """Test deleting a search index."""
        service = SearchService(db_session)
        item_id = uuid.uuid4()

        # Create index
        await service.index_item(
            item_type="card",
            item_id=str(item_id),
            title="To be deleted"
        )

        # Delete index
        result = await service.delete_index("card", str(item_id))

        assert result is True

        # Verify deletion
        index = await service.get_index("card", str(item_id))
        assert index is None
        print(f"✅ Deleted search index: card:{item_id}")

    async def test_delete_index_not_found(self, db_session):
        """Test deleting a non-existent index."""
        service = SearchService(db_session)

        result = await service.delete_index("card", str(uuid.uuid4()))

        assert result is False
        print("✅ delete_index returns False for non-existent index")

    async def test_bulk_index_items(self, db_session):
        """Test bulk indexing multiple items."""
        service = SearchService(db_session)

        items = [
            {
                "item_type": "card",
                "item_id": str(uuid.uuid4()),
                "title": f"Card {i}",
                "content": f"Content for card {i}",
                "tags": ["bulk", "test"]
            }
            for i in range(5)
        ]

        indexed_count = await service.bulk_index_items(items)

        assert indexed_count == 5
        print(f"✅ Bulk indexed {indexed_count} items")

    async def test_rebuild_index(self, db_session):
        """Test rebuilding search index."""
        service = SearchService(db_session)

        # Create some indices
        for i in range(3):
            await service.index_item(
                item_type="card",
                item_id=str(uuid.uuid4()),
                title=f"Card {i}"
            )

        # Rebuild
        count = await service.rebuild_index()

        assert count >= 3
        print(f"✅ Rebuilt {count} search indices")

    async def test_list_indices(self, db_session):
        """Test listing search indices."""
        service = SearchService(db_session)

        # Create indices of different types
        await service.index_item(
            item_type="card",
            item_id=str(uuid.uuid4()),
            title="Card 1"
        )
        await service.index_item(
            item_type="task",
            item_id=str(uuid.uuid4()),
            title="Task 1"
        )

        # List all indices
        indices = await service.list_indices()

        assert len(indices) >= 2
        print(f"✅ Listed {len(indices)} indices")

    async def test_list_indices_filtered(self, db_session):
        """Test listing indices with type filter."""
        service = SearchService(db_session)

        # Create indices
        await service.index_item(
            item_type="card",
            item_id=str(uuid.uuid4()),
            title="Card 1"
        )
        await service.index_item(
            item_type="task",
            item_id=str(uuid.uuid4()),
            title="Task 1"
        )

        # List only cards
        cards = await service.list_indices(item_type="card")

        assert all(c.item_type == "card" for c in cards)
        print(f"✅ Listed {len(cards)} card indices")

    async def test_get_index_stats(self, db_session):
        """Test getting index statistics."""
        service = SearchService(db_session)

        # Create indices
        for i in range(3):
            await service.index_item(
                item_type="card",
                item_id=str(uuid.uuid4()),
                title=f"Card {i}"
            )

        # Get stats
        stats = await service.get_index_stats()

        assert "by_type" in stats
        assert "total" in stats
        assert stats["total"] >= 3
        print(f"✅ Got index stats: {stats}")


@pytest.mark.asyncio
class TestSearchEngine:
    """Test SearchEngine functionality."""

    async def test_simple_text_search(self, db_session):
        """Test simple full-text search."""
        service = SearchService(db_session)
        engine = SearchEngine(db_session)

        # Create test indices
        await service.index_item(
            item_type="card",
            item_id=str(uuid.uuid4()),
            title="Python Programming Guide",
            content="Learn Python programming from scratch"
        )
        await service.index_item(
            item_type="card",
            item_id=str(uuid.uuid4()),
            title="JavaScript Tutorial",
            content="Learn JavaScript web development"
        )

        # Search for "Python"
        query = SearchQuery(query="Python")
        result = await engine.search(query)

        assert result.total >= 1
        assert len(result.results) >= 1
        assert any("Python" in r.title for r in result.results)
        print(f"✅ Search found {result.total} results for 'Python'")

    async def test_search_with_content(self, db_session):
        """Test search in content field."""
        service = SearchService(db_session)
        engine = SearchEngine(db_session)

        item_id = uuid.uuid4()
        await service.index_item(
            item_type="note",
            item_id=str(item_id),
            title="Meeting Notes",
            content="Discussed project timeline and deliverables"
        )

        # Search for content word
        query = SearchQuery(query="timeline")
        result = await engine.search(query)

        assert result.total >= 1
        assert any("timeline" in r.content_snippet.lower() for r in result.results)
        print(f"✅ Search found content match")

    async def test_search_with_type_filter(self, db_session):
        """Test search with item type filter."""
        service = SearchService(db_session)
        engine = SearchEngine(db_session)

        # Create different types
        await service.index_item(
            item_type="card",
            item_id=str(uuid.uuid4()),
            title="Design Card",
            content="UI design principles"
        )
        await service.index_item(
            item_type="task",
            item_id=str(uuid.uuid4()),
            title="Design Task",
            content="Complete UI design"
        )

        # Search only cards
        query = SearchQuery(query="Design", item_types=["card"])
        result = await engine.search(query)

        assert all(r.item_type == "card" for r in result.results)
        print(f"✅ Search filtered by type: {len(result.results)} card results")

    async def test_search_with_tag_filter(self, db_session):
        """Test search with tag filter."""
        service = SearchService(db_session)
        engine = SearchEngine(db_session)

        # Create items with different tags
        await service.index_item(
            item_type="card",
            item_id=str(uuid.uuid4()),
            title="Project Alpha",
            content="First project",
            tags=["alpha", "urgent"]
        )
        await service.index_item(
            item_type="card",
            item_id=str(uuid.uuid4()),
            title="Project Beta",
            content="Second project",
            tags=["beta", "normal"]
        )

        # Search by tag
        query = SearchQuery(query="Project", tags=["urgent"])
        result = await engine.search(query)

        # Should only return items with "urgent" tag
        assert all("urgent" in r.tags for r in result.results)
        print(f"✅ Search filtered by tag: {len(result.results)} results")

    async def test_search_pagination(self, db_session):
        """Test search pagination."""
        service = SearchService(db_session)
        engine = SearchEngine(db_session)

        # Create multiple items
        for i in range(25):
            await service.index_item(
                item_type="card",
                item_id=str(uuid.uuid4()),
                title=f"Card {i}",
                content=f"Content {i}"
            )

        # Search with pagination
        query = SearchQuery(query="Card", page=1, page_size=10)
        result = await engine.search(query)

        assert result.page == 1
        assert result.page_size == 10
        assert len(result.results) <= 10
        assert result.total >= 25
        print(f"✅ Pagination: page {result.page} showing {len(result.results)}/{result.total} results")

    async def test_search_sort_by_date(self, db_session):
        """Test search sorting by date."""
        service = SearchService(db_session)
        engine = SearchEngine(db_session)

        # Create items with different timestamps
        import time
        for i in range(3):
            await service.index_item(
                item_type="card",
                item_id=str(uuid.uuid4()),
                title=f"Card {i}"
            )
            await db_session.commit()
            time.sleep(0.01)  # Small delay to ensure different timestamps

        # Search sorted by date
        query = SearchQuery(query="Card", sort_by="-date")
        result = await engine.search(query)

        # Most recent first
        if len(result.results) >= 2:
            assert result.results[0].created_at >= result.results[1].created_at
        print(f"✅ Search sorted by -date (newest first)")

    async def test_search_snippet_generation(self, db_session):
        """Test content snippet generation."""
        service = SearchService(db_session)
        engine = SearchEngine(db_session)

        # Create item with long content
        long_content = "This is a very long content that contains the search term " * 10
        item_id = uuid.uuid4()
        await service.index_item(
            item_type="note",
            item_id=str(item_id),
            title="Long Note",
            content=long_content
        )

        # Search and check snippet
        query = SearchQuery(query="search term")
        result = await engine.search(query)

        assert len(result.results) >= 1
        snippet = result.results[0].content_snippet
        assert "search term" in snippet.lower()
        assert len(snippet) <= 300  # Snippet should be truncated
        print(f"✅ Snippet generated: '{snippet[:50]}...'")

    async def test_search_scoring(self, db_session):
        """Test search relevance scoring."""
        service = SearchService(db_session)
        engine = SearchEngine(db_session)

        # Create items with varying relevance
        await service.index_item(
            item_type="card",
            item_id=str(uuid.uuid4()),
            title="Python Programming",  # Exact match in title
            content="Learn Python"
        )
        await service.index_item(
            item_type="card",
            item_id=str(uuid.uuid4()),
            title="General Programming",  # Match in content only
            content="Python and other languages"
        )

        # Search
        query = SearchQuery(query="Python")
        result = await engine.search(query)

        # All results should have scores
        assert all(hasattr(r, 'score') for r in result.results)
        assert all(r.score > 0 for r in result.results)
        print(f"✅ Search results have scores: {[r.score for r in result.results]}")

    async def test_delete_by_item(self, db_session):
        """Test deleting index via SearchEngine."""
        service = SearchService(db_session)
        engine = SearchEngine(db_session)

        item_id = uuid.uuid4()
        await service.index_item(
            item_type="card",
            item_id=str(item_id),
            title="To be deleted"
        )

        # Delete via engine
        result = await engine.delete_by_item("card", str(item_id))

        assert result is True

        # Verify deletion
        index = await service.get_index("card", str(item_id))
        assert index is None
        print(f"✅ Deleted index via SearchEngine")


@pytest.mark.asyncio
class TestSearchIntegration:
    """Integration tests for search functionality."""

    async def test_full_search_workflow(self, db_session):
        """Test complete workflow: index, search, update, delete."""
        service = SearchService(db_session)
        engine = SearchEngine(db_session)

        # 1. Create index
        item_id = uuid.uuid4()
        index = await service.index_item(
            item_type="card",
            item_id=str(item_id),
            title="Integration Test Card",
            content="Testing full search workflow"
        )
        assert index.id is not None

        # 2. Search and find it
        query = SearchQuery(query="Integration Test")
        result = await engine.search(query)
        assert result.total >= 1

        # 3. Update index
        updated = await service.index_item(
            item_type="card",
            item_id=str(item_id),
            title="Updated Integration Test Card"
        )
        assert "Updated" in updated.title

        # 4. Search again and verify update
        query = SearchQuery(query="Updated Integration")
        result = await engine.search(query)
        assert result.total >= 1
        assert any("Updated" in r.title for r in result.results)

        # 5. Delete index
        deleted = await service.delete_index("card", str(item_id))
        assert deleted is True

        # 6. Verify deletion
        query = SearchQuery(query="Integration Test")
        result = await engine.search(query)
        assert not any("Integration Test Card" in r.title for r in result.results)

        print("✅ Full search workflow completed successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
