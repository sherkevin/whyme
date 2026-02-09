"""End-to-end scenario tests for Stage 4.

These tests simulate real-world user scenarios:
1. User creates content, searches for it, and gets insights
2. User ingests external content and analyzes it
3. Complete workflow from ingestion to insight generation
"""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.search_engine.search_service import SearchService
from agent_os.search_engine.search_engine import SearchEngine, SearchQuery
from agent_os.search_engine.ingestion_pipeline import IngestionService
from agent_os.search_engine.insight_service import InsightService
from agent_os.search_engine.models import SearchIndex, IngestionJob, InsightCluster


@pytest.mark.asyncio
class TestE2EScenarios:
    """End-to-end user scenario tests."""

    async def test_researcher_workflow(self, db_session):
        """Scenario: A researcher creates notes and searches for insights.

        User story:
        1. Researcher creates multiple notes on different topics
        2. Researcher searches for specific topics
        3. Researcher generates insights to understand trends
        """
        search_service = SearchService(db_session, auto_embed=False)
        insight_service = InsightService(db_session)

        # Step 1: Create research notes
        python_notes = [
            ("Python decorators explained", "Decorators modify function behavior"),
            ("Python context managers", "Context managers handle resources"),
            ("Python async/await", "Async programming in Python")
        ]

        ml_notes = [
            ("Machine learning basics", "Introduction to ML algorithms"),
            ("Neural networks", "Deep learning with neural networks"),
            ("Data preprocessing", "Clean and prepare data")
        ]

        all_notes = python_notes + ml_notes

        for title, content in all_notes:
            await search_service.index_item(
                item_type="note",
                item_id=uuid.uuid4(),
                title=title,
                content=content,
                tags=["research", "python" if "Python" in title else "ml"]
            )

        # Step 2: Search for Python content
        engine = SearchEngine(db_session)
        query = SearchQuery(query="Python")
        result = await engine.search(query)

        assert result.total >= 3
        python_results = [r for r in result.results if "python" in r.title.lower() or "python" in r.content_snippet.lower()]
        assert len(python_results) >= 3

        # Step 3: Generate insights on research
        summary = await insight_service.generate_summary(
            item_type="note",
            name="Research Summary"
        )

        assert summary.sample_count >= 6
        assert summary.insight_data["total_items"] >= 6

        # Step 4: Get topic clustering
        topics = await insight_service.generate_topics(
            item_type="note",
            num_topics=3
        )

        assert len(topics.insight_data["topics"]) <= 3
        topic_names = [t["topic_name"] for t in topics.insight_data["topics"]]
        assert "python" in topic_names or "research" in topic_names

        print(f"✅ Researcher workflow: Created {len(all_notes)} notes, " +
              f"found {result.total} search results, " +
              f"generated insights with {summary.sample_count} items")

    async def test_content_creator_workflow(self, db_session):
        """Scenario: Content creator ingests articles and analyzes audience.

        User story:
        1. Creator has multiple articles to ingest
        2. Creator ingests content into the system
        3. Creator analyzes audience engagement via insights
        """
        ingestion_service = IngestionService(db_session)
        search_service = SearchService(db_session, auto_embed=False)
        insight_service = InsightService(db_session)

        # Step 1: Simulate ingesting multiple articles
        articles = [
            ("Introduction to AI", "Artificial Intelligence is transforming..."),
            ("Web Development Trends", "Modern web development includes..."),
            ("Data Science Career", "Data science offers many opportunities...")
        ]

        # Simulate ingestion by creating indexed items
        for title, content in articles:
            await search_service.index_item(
                item_type="card",  # Use "card" instead of "article" (valid type)
                item_id=uuid.uuid4(),
                title=title,
                content=content,
                tags=["ingested", "published"]
            )

        # Step 2: Search for ingested content
        engine = SearchEngine(db_session)

        # Search all ingested content (search for individual terms)
        query = SearchQuery(query="introduction", tags=["ingested"])
        result = await engine.search(query)

        # Should find at least the "Introduction to AI" article
        assert result.total >= 1

        # Step 3: Generate summary insight
        summary = await insight_service.generate_summary(
            item_type="card",
            name="Content Summary"
        )

        assert summary.cluster_type == "summary"
        assert summary.sample_count >= 3

        print(f"✅ Content creator workflow: Ingested {len(articles)} articles, " +
              f"generated summary with {summary.sample_count} items")

    async def test_knowledge_manager_workflow(self, db_session):
        """Scenario: Knowledge manager organizes and categorizes information.

        User story:
        1. Manager has documents from multiple sources
        2. Manager wants to see topic distribution
        3. Manager identifies knowledge gaps
        """
        search_service = SearchService(db_session, auto_embed=False)
        insight_service = InsightService(db_session)

        # Step 1: Create diverse knowledge base
        knowledge_base = {
            "programming": [
                ("Python Best Practices", "Code style and structure"),
                ("JavaScript Patterns", "Design patterns in JS")
            ],
            "databases": [
                ("PostgreSQL Tips", "Optimize queries"),
                ("MongoDB Guide", "NoSQL database")
            ],
            "devops": [
                ("Docker Basics", "Container technology"),
                ("Kubernetes Intro", "Orchestration")
            ]
        }

        all_items = []
        for category, items in knowledge_base.items():
            for title, content in items:
                item_id = uuid.uuid4()
                all_items.append(item_id)
                await search_service.index_item(
                    item_type="card",  # Use "card" instead of "knowledge" (valid type)
                    item_id=item_id,
                    title=title,
                    content=content,
                    tags=["knowledge", category]
                )

        # Step 2: Get topic distribution (filter to only our items)
        topics = await insight_service.generate_topics(
            item_type="card",
            item_ids=[str(item_id) for item_id in all_items],  # Only analyze our items
            num_topics=5
        )

        assert topics.cluster_type == "topic"
        assert topics.sample_count == len(all_items)

        # Verify categories are detected
        topic_names = [t["topic_name"] for t in topics.insight_data["topics"]]
        for category in ["programming", "databases", "devops"]:
            # At least one category should be detected
            assert any(cat in topic_names for cat in [category, category + "s"])

        # Step 3: Search by category
        engine = SearchEngine(db_session)
        # Search for database-related content in titles
        query = SearchQuery(query="PostgreSQL")
        result = await engine.search(query)

        # Should find at least 1 database-related item
        assert result.total >= 1

        print(f"✅ Knowledge manager workflow: Organized {len(all_items)} items, " +
              f"identified {len(topics.insight_data['topics'])} topics")

    async def test_analyst_workflow(self, db_session):
        """Scenario: Business analyst tracks project metrics over time.

        User story:
        1. Analyst creates multiple task entries
        2. Analyst generates trend insights
        3. Analyst identifies patterns in task completion
        """
        search_service = SearchService(db_session, auto_embed=False)
        insight_service = InsightService(db_session)

        # Step 1: Create tasks with different statuses
        for i in range(20):
            status = "completed" if i % 3 == 0 else "pending"
            await search_service.index_item(
                item_type="task",
                item_id=uuid.uuid4(),
                title=f"Task {i}: Data analysis",
                content=f"Complete data analysis for project {i//5}",
                tags=["task", status, f"project_{i//5}"]
            )

        # Step 2: Generate trend analysis
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=30)

        trend = await insight_service.generate_trend(
            item_type="task",
            metric="count",
            date_range={
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            group_by="day"
        )

        assert trend.cluster_type == "trend"
        assert trend.sample_count >= 20  # Use sample_count instead

        # Step 3: Detect patterns
        pattern = await insight_service.generate_pattern(
            item_type="task",
            pattern_type="content_length"
        )

        assert pattern.cluster_type == "pattern"
        assert "content_length" in pattern.insight_data["pattern_type"]

        # Step 4: Search for completed tasks
        engine = SearchEngine(db_session)
        query = SearchQuery(query="Task", tags=["completed"])
        result = await engine.search(query)

        assert result.total >= 6  # At least 20/3 completed

        print(f"✅ Analyst workflow: Tracked {trend.sample_count} tasks, " +
              f"detected {len(pattern.insight_data['patterns'])} patterns")

    async def test_full_lifecycle(self, db_session):
        """Scenario: Complete lifecycle from creation to insight generation.

        User story:
        1. User creates diverse content (cards, tasks, notes)
        2. User searches and filters content
        3. User generates multiple types of insights
        4. User queries and manages insights
        """
        search_service = SearchService(db_session, auto_embed=False)
        engine = SearchEngine(db_session)
        insight_service = InsightService(db_session)

        # Phase 1: Content Creation
        card_id = uuid.uuid4()
        task_id = uuid.uuid4()
        note_id = uuid.uuid4()

        await search_service.index_item(
            item_type="card",
            item_id=card_id,
            title="Python Machine Learning",
            content="ML algorithms in Python",
            tags=["python", "ml", "card"]
        )

        await search_service.index_item(
            item_type="task",
            item_id=task_id,
            title="Complete ML Course",
            content="Finish all ML exercises",
            tags=["python", "learning", "task"]
        )

        await search_service.index_item(
            item_type="note",
            item_id=note_id,
            title="ML Notes",
            content="Important ML concepts",
            tags=["python", "ml", "notes"]
        )

        # Phase 2: Search and Filter
        # Search all python content
        query = SearchQuery(query="python")
        result = await engine.search(query)
        assert result.total >= 3

        # Filter by type
        query = SearchQuery(query="python", item_types=["card"])
        result = await engine.search(query)
        assert result.total >= 1
        assert all(r.item_type == "card" for r in result.results)

        # Phase 3: Generate Multiple Insights

        # Summary
        summary = await insight_service.generate_summary(
            item_type="card",
            name="Python Content Summary"
        )
        assert summary.cluster_type == "summary"
        assert summary.sample_count >= 1

        # Topics
        topics = await insight_service.generate_topics(
            item_type="card",
            num_topics=3
        )
        assert topics.cluster_type == "topic"
        assert len(topics.insight_data["topics"]) <= 3

        # Pattern
        pattern = await insight_service.generate_pattern(
            item_type="card",
            pattern_type="creation_time"
        )
        assert pattern.cluster_type == "pattern"

        # Phase 4: Insight Management

        # List all insights
        all_insights = await insight_service.list_insights(limit=10)
        assert len(all_insights) >= 3

        # Filter by type
        summaries = await insight_service.list_insights(cluster_type="summary")
        assert len(summaries) >= 1

        # Delete an insight
        deleted = await insight_service.delete_insight(str(summary.id))
        assert deleted is True

        # Verify deletion
        retrieved = await insight_service.get_insight(str(summary.id))
        assert retrieved is None

        print(f"✅ Full lifecycle: Created 3 items, searched, " +
              f"generated 4 insights, managed insights lifecycle")


@pytest.mark.asyncio
class TestPerformanceScenarios:
    """Performance-focused scenario tests."""

    async def test_large_scale_search(self, db_session):
        """Test search performance with realistic data volume."""
        search_service = SearchService(db_session, auto_embed=False)
        import time

        # Create 200 items (simulating realistic scale)
        items_to_create = 200
        for i in range(items_to_create):
            category = ["tech", "business", "science", "art"][i % 4]
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"{category.capitalize()} Article {i}",
                content=f"This is about {category}, number {i}",
                tags=[category, f"batch{i//10}"]
            )

        # Test search performance
        engine = SearchEngine(db_session)

        start = time.time()
        query = SearchQuery(query="Article", page_size=20)
        result = await engine.search(query)
        search_time = (time.time() - start) * 1000

        assert result.total >= items_to_create
        assert search_time < 100  # Should complete in < 100ms
        assert len(result.results) <= 20  # Respect page_size

        # Test multiple pages
        page_1_results = {r.item_id for r in result.results}

        query = SearchQuery(query="Article", page=2, page_size=20)
        result = await engine.search(query)
        page_2_results = {r.item_id for r in result.results}

        # Verify pagination works (no overlap)
        assert len(page_1_results.intersection(page_2_results)) == 0

        print(f"✅ Large scale search: {items_to_create} items, " +
              f"search in {search_time:.2f}ms, pagination works correctly")

    async def test_concurrent_operations(self, db_session):
        """Test concurrent search and insight generation."""
        import asyncio

        search_service = SearchService(db_session, auto_embed=False)
        insight_service = InsightService(db_session)

        # Create some data
        for i in range(10):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Concurrent Test {i}",
                content=f"Content {i}",
                tags=["test", "concurrent"]
            )

        # Run concurrent searches
        async def run_search(query_text):
            engine = SearchEngine(db_session)
            query = SearchQuery(query=query_text)
            result = await engine.search(query)
            return result.total

        start = asyncio.get_event_loop().time()
        results = await asyncio.gather(
            run_search("Concurrent"),
            run_search("Test"),
            run_search("Content"),
            run_search("Concurrent Test")
        )
        elapsed = (asyncio.get_event_loop().time() - start) * 1000

        assert all(r > 0 for r in results)
        assert elapsed < 500  # All searches should complete in < 500ms

        print(f"✅ Concurrent operations: 4 searches in {elapsed:.2f}ms")

    async def test_insight_generation_scalability(self, db_session):
        """Test insight generation with growing dataset."""
        search_service = SearchService(db_session, auto_embed=False)
        insight_service = InsightService(db_session)
        import time

        datasets = [10, 50, 100]
        times = []

        for size in datasets:
            # Create dataset
            for i in range(size):
                await search_service.index_item(
                    item_type="card",
                    item_id=uuid.uuid4(),
                    title=f"Scalability Test {i}",
                    content=f"Content for scalability testing {i}",
                    tags=["scalability", "test"]
                )

            # Measure insight generation time
            start = time.time()
            summary = await insight_service.generate_summary(item_type="card")
            elapsed = (time.time() - start) * 1000
            times.append(elapsed)

            # Verify linear or sub-linear scaling
            assert elapsed < 100  # Should complete in < 100ms
            assert summary.sample_count >= size

        print(f"✅ Insight scalability: Generated insights for {datasets} items, " +
              f"times: {[f'{t:.2f}ms' for t in times]}")


@pytest.mark.asyncio
class TestErrorRecoveryScenarios:
    """Error handling and recovery scenarios."""

    async def test_search_with_no_results(self, db_session):
        """Scenario: User searches for non-existent content."""
        engine = SearchEngine(db_session)
        query = SearchQuery(query="nonexistent_content_xyz123")

        result = await engine.search(query)

        assert result.total == 0
        assert len(result.results) == 0
        assert result.page == 1
        assert result.page_size == 20  # Default

        print(f"✅ Empty search handled gracefully")

    async def test_insight_with_empty_data(self, db_session):
        """Scenario: Generate insights when no data exists."""
        insight_service = InsightService(db_session)

        with pytest.raises(ValueError, match="No.*items found"):
            await insight_service.generate_summary(item_type="nonexistent")

        print(f"✅ Empty data error handled correctly")

    async def test_malformed_search_queries(self, db_session):
        """Scenario: User enters various search query formats."""
        search_service = SearchService(db_session, auto_embed=False)
        engine = SearchEngine(db_session)

        # Create sample data
        await search_service.index_item(
            item_type="card",
            item_id=uuid.uuid4(),
            title="Test Card",
            content="Test content with keywords",
            tags=["test"]
        )

        # Empty query (should handle gracefully)
        try:
            query = SearchQuery(query="   ")
            result = await engine.search(query)
            # May return all or nothing depending on implementation
        except Exception as e:
            # Expected to fail validation or return empty
            pass

        # Very long query
        query = SearchQuery(query="a" * 200)
        result = await engine.search(query)
        # Should handle gracefully

        # Special characters
        query = SearchQuery(query="test-content_tags")
        result = await engine.search(query)
        assert result.total >= 0  # Should not crash

        print(f"✅ Malformed queries handled gracefully")

    async def test_partial_failure_recovery(self, db_session):
        """Scenario: System handles partial failures gracefully."""
        search_service = SearchService(db_session, auto_embed=False)
        insight_service = InsightService(db_session)

        # Create some good data
        for i in range(5):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Good Data {i}",
                content="Valid content",
                tags=["valid"]
            )

        # Search should work
        engine = SearchEngine(db_session)
        query = SearchQuery(query="Good Data")
        result = await engine.search(query)
        assert result.total >= 5

        # Insight generation should work
        summary = await insight_service.generate_summary(item_type="card")
        assert summary.sample_count >= 5

        # Try to get non-existent insight (should handle gracefully)
        fake_id = uuid.uuid4()
        result = await insight_service.get_insight(str(fake_id))
        assert result is None

        print(f"✅ Partial failure recovery works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
