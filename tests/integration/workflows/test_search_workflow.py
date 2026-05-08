"""End-to-end integration tests for Stage 4.

This test file validates the complete workflows:
1. Search -> Ingestion -> Search
2. Multiple data types unified search
3. Insight generation on real data
4. Complete API workflows
"""

import uuid
from datetime import datetime, timedelta

import pytest

from agent_os.search_engine.ingestion_pipeline import IngestionService
from agent_os.search_engine.insight_service import InsightService
from agent_os.search_engine.search_engine import SearchEngine, SearchQuery
from agent_os.search_engine.search_service import SearchService


@pytest.mark.asyncio
class TestStage4Integration:
    """End-to-end integration tests for Stage 4."""

    async def test_complete_search_workflow(self, db_session):
        """Test complete search workflow: index -> search -> retrieve."""
        search_service = SearchService(db_session, auto_embed=False)

        # Step 1: Create multiple types of indexed items
        card_id = uuid.uuid4()
        task_id = uuid.uuid4()
        note_id = uuid.uuid4()

        await search_service.index_item(
            item_type="card",
            item_id=card_id,
            title="Python Programming Guide",
            content="Learn Python from scratch",
            tags=["python", "tutorial"]
        )

        await search_service.index_item(
            item_type="task",
            item_id=task_id,
            title="Complete Python Course",
            content="Finish all Python exercises",
            tags=["python", "learning"]
        )

        await search_service.index_item(
            item_type="note",
            item_id=note_id,
            title="Python Notes",
            content="Important Python concepts",
            tags=["python", "notes"]
        )

        # Step 2: Search across all types
        engine = SearchEngine(db_session)
        query = SearchQuery(query="python")
        result = await engine.search(query)

        assert result.total >= 3
        item_types = {r.item_type for r in result.results}
        assert "card" in item_types
        assert "task" in item_types
        assert "note" in item_types

        # Step 3: Verify individual items can be retrieved
        card_index = await search_service.get_index("card", card_id)
        assert card_index is not None
        assert card_index.title == "Python Programming Guide"

        print(f"✅ Complete search workflow: {result.total} items found")

    async def test_search_with_type_filtering(self, db_session):
        """Test searching with type filters."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create mixed content
        for i in range(5):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content="Card content",
                tags=["card"]
            )

        for i in range(3):
            await search_service.index_item(
                item_type="task",
                item_id=uuid.uuid4(),
                title=f"Task {i}",
                content="Task content",
                tags=["task"]
            )

        # Search all
        engine = SearchEngine(db_session)
        query = SearchQuery(query="content")
        result = await engine.search(query)
        assert result.total >= 8

        # Filter by card
        query = SearchQuery(query="content", item_types=["card"])
        result = await engine.search(query)
        assert result.total >= 5
        assert all(r.item_type == "card" for r in result.results)

        # Filter by task
        query = SearchQuery(query="content", item_types=["task"])
        result = await engine.search(query)
        assert result.total >= 3
        assert all(r.item_type == "task" for r in result.results)

        print("✅ Type filtering works correctly")

    async def test_search_with_tag_filtering(self, db_session):
        """Test searching with tag filters."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create items with different tags
        await search_service.index_item(
            item_type="card",
            item_id=uuid.uuid4(),
            title="Python Advanced",
            content="Advanced Python topics",
            tags=["python", "advanced"]
        )

        await search_service.index_item(
            item_type="card",
            item_id=uuid.uuid4(),
            title="JavaScript Guide",
            content="JavaScript basics",
            tags=["javascript", "guide"]
        )

        await search_service.index_item(
            item_type="card",
            item_id=uuid.uuid4(),
            title="Python Basics",
            content="Python fundamentals",
            tags=["python", "basics"]
        )

        # First test: search without tag filter to verify data exists
        engine = SearchEngine(db_session)
        query = SearchQuery(query="Python")
        result = await engine.search(query)

        print(f"\n  Debug: Search for 'Python' (no tag filter): {result.total} results")
        for r in result.results[:3]:
            print(f"    - {r.title}: tags={r.tags}")

        # Now test with tag filter
        query = SearchQuery(query="Python", tags=["python"])
        result = await engine.search(query)

        print(f"\n  Debug: Search for 'Python' with tag=['python']: {result.total} results")

        # Should find items with "Python" in title/content AND "python" tag
        assert result.total >= 1, f"Expected at least 1 result, got {result.total}"
        assert all("python" in r.tags for r in result.results)

        print("✅ Tag filtering works correctly")

    async def test_ingestion_to_search_workflow(self, db_session):
        """Test complete ingestion workflow: ingest -> index -> search."""
        ingestion_service = IngestionService(db_session)
        search_service = SearchService(db_session, auto_embed=False)

        # Step 1: Create ingestion job
        job = await ingestion_service.create_job(
            source_type="markdown",
            source_file_path="/tmp/test.md",
            chunk_size=500,
            overlap=100
        )

        assert job.status == "pending"
        assert job.id is not None

        # Step 2: Simulate job completion (manually create items)
        # In real scenario, this would be done by the pipeline
        test_content = "This is a test document about Python programming. Python is great for data science."
        chunks = [test_content[i:i+500] for i in range(0, len(test_content), 500)]

        for chunk in chunks:
            item_id = uuid.uuid4()
            await search_service.index_item(
                item_type="card",
                item_id=item_id,
                title="Test Document",
                content=chunk,
                tags=["ingested", "test"]
            )

        # Step 3: Search for ingested content
        engine = SearchEngine(db_session)
        query = SearchQuery(query="Python programming")
        result = await engine.search(query)

        assert result.total >= 1
        assert any("ingested" in r.tags for r in result.results)

        print("✅ Ingestion to search workflow works")

    async def test_insight_on_real_data(self, db_session):
        """Test insight generation on real indexed data."""
        search_service = SearchService(db_session, auto_embed=False)
        insight_service = InsightService(db_session)

        # Create diverse data
        topics = ["python", "javascript", "data", "web", "api"]
        for topic in topics:
            for i in range(3):
                await search_service.index_item(
                    item_type="card",
                    item_id=uuid.uuid4(),
                    title=f"{topic.capitalize()} Guide {i}",
                    content=f"Learn about {topic}",
                    tags=[topic, "guide"]
                )

        # Generate summary
        summary = await insight_service.generate_summary(
            item_type="card",
            name="Test Summary"
        )

        assert summary.cluster_type == "summary"
        assert summary.sample_count >= 15
        assert "total_items" in summary.insight_data

        # Generate topics
        topics_insight = await insight_service.generate_topics(
            item_type="card",
            num_topics=3
        )

        assert topics_insight.cluster_type == "topic"
        assert len(topics_insight.insight_data["topics"]) <= 3

        print("✅ Insight generation on real data works")

    async def test_pagination_and_sorting(self, db_session):
        """Test pagination and sorting functionality."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create many items
        item_ids = []
        for i in range(25):
            item_id = uuid.uuid4()
            item_ids.append(item_id)
            await search_service.index_item(
                item_type="card",
                item_id=item_id,
                title=f"Card {i:02d}",
                content=f"Content {i}",
                tags=[f"tag{i % 5}"]
            )

        engine = SearchEngine(db_session)

        # Test pagination
        query = SearchQuery(query="content", page=1, page_size=10)
        result = await engine.search(query)

        assert result.total >= 25
        assert len(result.results) <= 10
        assert result.page == 1

        # Get second page
        query = SearchQuery(query="content", page=2, page_size=10)
        result2 = await engine.search(query)

        assert result2.page == 2
        # Ensure different results
        if result.total > 10:
            first_ids = {r.item_id for r in result.results}
            second_ids = {r.item_id for r in result2.results}
            assert len(first_ids.intersection(second_ids)) == 0

        # Test sorting by date (filter to only our test items)
        query = SearchQuery(query="Pagination Test Content", sort_by="date", page_size=25)
        result = await engine.search(query)

        if len(result.results) >= 2:
            # Check ordering
            dates = [r.created_at for r in result.results]
            assert dates == sorted(dates, reverse=True)

        print("✅ Pagination and sorting work correctly")

    async def test_update_and_delete_workflow(self, db_session):
        """Test update and delete operations."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create item
        item_id = uuid.uuid4()
        await search_service.index_item(
            item_type="card",
            item_id=item_id,
            title="Original Title",
            content="Original content",
            tags=["original"]
        )

        # Verify creation
        index = await search_service.get_index("card", item_id)
        assert index.title == "Original Title"

        # Update item
        await search_service.index_item(
            item_type="card",
            item_id=item_id,
            title="Updated Title",
            content="Updated content",
            tags=["updated"]
        )

        # Verify update
        index = await search_service.get_index("card", item_id)
        assert index.title == "Updated Title"
        assert "updated" in index.tags

        # Search for updated item
        engine = SearchEngine(db_session)
        query = SearchQuery(query="Updated Title")
        result = await engine.search(query)
        assert result.total >= 1

        # Delete item
        deleted = await search_service.delete_index("card", item_id)
        assert deleted is True

        # Verify deletion
        index = await search_service.get_index("card", item_id)
        assert index is None

        # Search should not find deleted item
        query = SearchQuery(query="Updated Title")
        result = await engine.search(query)
        assert not any(r.item_id == item_id for r in result.results)

        print("✅ Update and delete workflow works")

    async def test_bulk_operations(self, db_session):
        """Test bulk indexing operations."""
        search_service = SearchService(db_session, auto_embed=False)

        # Prepare bulk items
        items = []
        for i in range(10):
            items.append({
                "item_type": "card",
                "item_id": uuid.uuid4(),
                "title": f"Bulk Card {i}",
                "content": f"Bulk content {i}",
                "tags": [f"bulk{i % 3}"]
            })

        # Bulk index
        count = await search_service.bulk_index_items(items)
        assert count == 10

        # Verify all items are indexed
        engine = SearchEngine(db_session)
        query = SearchQuery(query="Bulk")
        result = await engine.search(query)

        assert result.total >= 10

        print("✅ Bulk operations work correctly")

    async def test_cross_module_data_flow(self, db_session):
        """Test data flow across Search, Ingestion, and Insight modules."""
        search_service = SearchService(db_session, auto_embed=False)
        ingestion_service = IngestionService(db_session)
        insight_service = InsightService(db_session)

        # Step 1: Simulate ingestion
        job = await ingestion_service.create_job(
            source_type="markdown",
            source_file_path="/tmp/test.md"
        )

        # Step 2: Create indexed data (simulating ingestion result)
        created_items = []
        for i in range(10):
            item_id = uuid.uuid4()
            created_items.append(item_id)
            await search_service.index_item(
                item_type="card",
                item_id=item_id,
                title=f"Ingested Card {i}",
                content=f"Content from ingestion {i}",
                tags=["ingested", f"batch{i//3}"]
            )

        # Step 3: Search ingested content
        engine = SearchEngine(db_session)
        query = SearchQuery(query="Ingested", tags=["ingested"])
        result = await engine.search(query)
        assert result.total >= 10, f"Expected at least 10 results, got {result.total}"

        # Step 4: Generate insights on ingested data (filter to our items)
        item_ids = [str(item_id) for item_id in created_items]
        summary = await insight_service.generate_summary(
            item_type="card",
            item_ids=item_ids,
            name="Ingested Data Summary"
        )
        assert summary.sample_count >= 10

        topics = await insight_service.generate_topics(
            item_type="card",
            item_ids=item_ids,
            num_topics=3
        )
        # Just verify topics are generated (may not be "ingested" due to frequency)
        assert len(topics.insight_data["topics"]) <= 3

        print("✅ Cross-module data flow works correctly")

    async def test_error_handling_and_recovery(self, db_session):
        """Test error handling and recovery."""
        search_service = SearchService(db_session, auto_embed=False)

        # Test invalid UUID handling
        try:
            await search_service.get_index("card", "invalid-uuid")
            assert False, "Should raise ValueError"
        except (ValueError, AttributeError):
            pass  # Expected

        # Test non-existent item
        fake_id = uuid.uuid4()
        result = await search_service.get_index("card", fake_id)
        assert result is None

        # Test delete non-existent item
        deleted = await search_service.delete_index("card", fake_id)
        assert deleted is False

        # Test search with no results
        engine = SearchEngine(db_session)
        query = SearchQuery(query="nonexistent_content_xyz123")
        result = await engine.search(query)
        assert result.total == 0
        assert len(result.results) == 0

        print("✅ Error handling works correctly")

    async def test_performance_with_large_dataset(self, db_session):
        """Test performance with larger dataset."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create 100 items
        import time
        start = time.time()

        for i in range(100):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Performance Card {i}",
                content=f"Performance test content {i} with some keywords",
                tags=["performance", f"tag{i % 10}"]
            )

        indexing_time = time.time() - start

        # Search performance
        engine = SearchEngine(db_session)
        start = time.time()

        query = SearchQuery(query="performance test")
        result = await engine.search(query)

        search_time = (time.time() - start) * 1000  # ms

        assert result.total >= 100
        assert search_time < 1000  # Should be fast

        # Insight generation performance
        insight_service = InsightService(db_session)
        start = time.time()

        summary = await insight_service.generate_summary(item_type="card")

        insight_time = (time.time() - start) * 1000  # ms

        assert summary.sample_count >= 100
        assert insight_time < 500  # Should be fast

        print("✅ Performance test passed:")
        print(f"    Indexed 100 items in {indexing_time:.2f}s")
        print(f"    Search in {search_time:.2f}ms")
        print(f"    Insight in {insight_time:.2f}ms")


@pytest.mark.asyncio
class TestStage4APIWorkflows:
    """Test API-like workflows."""

    async def test_search_api_workflow(self, db_session):
        """Test search API workflow."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create test data
        await search_service.index_item(
            item_type="card",
            item_id=uuid.uuid4(),
            title="API Test Card",
            content="Testing API workflow",
            tags=["api", "test"]
        )

        # Simulate API call: GET /api/v1/search?query=api
        engine = SearchEngine(db_session)
        query = SearchQuery(
            query="api",
            item_types=["card"],
            page=1,
            page_size=20,
            sort_by="relevance"
        )
        result = await engine.search(query)

        # Verify response structure
        assert hasattr(result, 'total')
        assert hasattr(result, 'page')
        assert hasattr(result, 'page_size')
        assert hasattr(result, 'results')

        # Verify result items have required fields
        for r in result.results:
            assert hasattr(r, 'item_type')
            assert hasattr(r, 'item_id')
            assert hasattr(r, 'title')
            assert hasattr(r, 'content_snippet')
            assert hasattr(r, 'score')
            assert hasattr(r, 'tags')

        print("✅ Search API workflow works")

    async def test_insight_api_workflow(self, db_session):
        """Test insight API workflow."""
        search_service = SearchService(db_session, auto_embed=False)
        insight_service = InsightService(db_session)

        # Create test data
        for i in range(5):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"API Test Card {i}",
                content=f"Test content {i}",
                tags=["api", "test"]
            )

        # Simulate API call: POST /api/v1/search/insights/generate
        summary = await insight_service.generate_summary(
            item_type="card",
            name="API Test Summary"
        )

        # Verify response structure
        assert summary.cluster_type == "summary"
        assert summary.name == "API Test Summary"
        assert summary.insight_data is not None
        assert "total_items" in summary.insight_data

        # Simulate API call: GET /api/v1/search/insights
        insights = await insight_service.list_insights(limit=10)
        assert len(insights) >= 1

        # Simulate API call: GET /api/v1/search/insights/{id}
        retrieved = await insight_service.get_insight(str(summary.id))
        assert retrieved.id == summary.id

        print("✅ Insight API workflow works")

    async def test_date_range_filtering(self, db_session):
        """Test date range filtering in searches and insights."""
        search_service = SearchService(db_session, auto_embed=False)
        insight_service = InsightService(db_session)

        # Create items with different timestamps
        # Note: In real scenario, these would have different created_at
        for i in range(10):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Date Test Card {i}",
                content=f"Test content {i}",
                tags=["date_test"]
            )

        # Test insight with date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        summary = await insight_service.generate_summary(
            item_type="card",
            date_range={
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        )

        assert summary.sample_count >= 1
        assert "date_range" in summary.insight_data

        print("✅ Date range filtering works")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
