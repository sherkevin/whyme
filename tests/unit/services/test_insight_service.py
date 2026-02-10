"""Unit tests for Stage 4 Insight Service."""

import pytest
from datetime import datetime, timedelta
from agent_os.search_engine.insight_service import InsightService
from agent_os.search_engine.models import SearchIndex, InsightCluster
from agent_os.search_engine.search_service import SearchService
import uuid


@pytest.mark.asyncio
class TestInsightService:
    """Test InsightService functionality."""

    async def test_generate_summary_basic(self, db_session):
        """Test basic summary generation."""
        # Create sample indexed items with unique tag to isolate test
        search_service = SearchService(db_session, auto_embed=False)
        unique_tag = f"test_summary_basic_{uuid.uuid4().hex[:8]}"

        for i in range(5):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Test Card {i}",
                content=f"This is test content for card {i}",
                tags=[f"tag{i}", unique_tag]
            )

        # Generate summary filtering by our unique tag
        # Note: Since we can't filter by tag in generate_summary, we'll just check the minimum
        insight_service = InsightService(db_session)
        summary = await insight_service.generate_summary(
            item_type="card",
            name="Test Summary"
        )

        assert summary is not None
        assert summary.cluster_type == "summary"
        assert summary.source_item_type == "card"
        assert summary.sample_count >= 5  # At least our 5 items
        assert summary.insight_data is not None
        assert "total_items" in summary.insight_data
        assert summary.insight_data["total_items"] >= 5
        print(f"✅ Summary generated: {summary.name} with {summary.sample_count} items")

    async def test_generate_summary_with_item_ids(self, db_session):
        """Test summary generation with specific item IDs."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create items
        item_ids = []
        for i in range(3):
            item_id = uuid.uuid4()
            item_ids.append(item_id)
            await search_service.index_item(
                item_type="card",
                item_id=item_id,
                title=f"Specific Card {i}",
                content=f"Content {i}",
                tags=["specific"]
            )

        # Add another item not in the list
        await search_service.index_item(
            item_type="card",
            item_id=uuid.uuid4(),
            title="Other Card",
            content="Other content",
            tags=["other"]
        )

        # Generate summary for specific items
        insight_service = InsightService(db_session)
        summary = await insight_service.generate_summary(
            item_type="card",
            item_ids=[str(idx) for idx in item_ids]
        )

        assert summary.sample_count == 3
        assert len(summary.source_item_ids) == 3
        print(f"✅ Summary with item_ids: {summary.sample_count} items")

    async def test_generate_summary_with_date_range(self, db_session):
        """Test summary generation with date range filter."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create items at different times
        now = datetime.utcnow()
        past_time = now - timedelta(days=10)

        # Recent item
        await search_service.index_item(
            item_type="card",
            item_id=uuid.uuid4(),
            title="Recent Card",
            content="Recent content",
            tags=["recent"]
        )

        # Old item (simulate by not creating - just test the filter works)
        # In real test, we'd mock created_at

        # Generate summary for recent items
        insight_service = InsightService(db_session)
        date_range = {
            "start": (now - timedelta(days=1)).isoformat(),
            "end": (now + timedelta(days=1)).isoformat()
        }

        summary = await insight_service.generate_summary(
            item_type="card",
            date_range=date_range
        )

        # Should include the recent item
        assert summary.sample_count >= 1
        print(f"✅ Summary with date_range: {summary.sample_count} items")

    async def test_generate_trend_by_day(self, db_session):
        """Test trend generation grouped by day."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create items spread across time
        for i in range(10):
            await search_service.index_item(
                item_type="task",
                item_id=uuid.uuid4(),
                title=f"Task {i}",
                content=f"Task content {i}",
                tags=["task"]
            )

        # Generate trend
        insight_service = InsightService(db_session)
        date_range = {
            "start": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "end": (datetime.utcnow() + timedelta(days=1)).isoformat()
        }

        trend = await insight_service.generate_trend(
            item_type="task",
            metric="count",
            date_range=date_range,
            group_by="day"
        )

        assert trend is not None
        assert trend.cluster_type == "trend"
        assert trend.source_item_type == "task"
        assert "trend_direction" in trend.insight_data
        assert trend.insight_data["metric"] == "count"
        assert trend.insight_data["group_by"] == "day"
        print(f"✅ Trend generated: {trend.name}, direction={trend.insight_data.get('trend_direction')}")

    async def test_generate_trend_by_week(self, db_session):
        """Test trend generation grouped by week."""
        search_service = SearchService(db_session, auto_embed=False)

        for i in range(5):
            await search_service.index_item(
                item_type="note",
                item_id=uuid.uuid4(),
                title=f"Note {i}",
                content="Note content",
                tags=["note"]
            )

        insight_service = InsightService(db_session)
        date_range = {
            "start": (datetime.utcnow() - timedelta(days=30)).isoformat(),
            "end": datetime.utcnow().isoformat()
        }

        trend = await insight_service.generate_trend(
            item_type="note",
            group_by="week",
            date_range=date_range
        )

        assert trend.insight_data["group_by"] == "week"
        print(f"✅ Weekly trend: {trend.insight_data.get('periods_analyzed')} periods")

    async def test_generate_topics(self, db_session):
        """Test topic clustering generation."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create items with different tags
        tag_groups = [
            ["python", "programming"],
            ["python", "tutorial"],
            ["javascript", "programming"],
            ["javascript", "web"],
            ["python", "advanced"]
        ]

        for i, tags in enumerate(tag_groups):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content="Content",
                tags=tags
            )

        # Generate topics
        insight_service = InsightService(db_session)
        topics = await insight_service.generate_topics(
            item_type="card",
            num_topics=3
        )

        assert topics is not None
        assert topics.cluster_type == "topic"
        assert topics.source_item_type == "card"
        assert "topics" in topics.insight_data
        assert len(topics.insight_data["topics"]) <= 3
        assert topics.insight_data["num_topics"] == 3
        print(f"✅ Topics generated: {len(topics.insight_data['topics'])} topics")

    async def test_generate_pattern_creation_time(self, db_session):
        """Test pattern detection for creation time."""
        search_service = SearchService(db_session, auto_embed=False)

        for i in range(5):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content="Content",
                tags=["pattern"]
            )

        insight_service = InsightService(db_session)
        pattern = await insight_service.generate_pattern(
            item_type="card",
            pattern_type="creation_time"
        )

        assert pattern is not None
        assert pattern.cluster_type == "pattern"
        assert "patterns" in pattern.insight_data
        assert isinstance(pattern.insight_data["patterns"], list)
        print(f"✅ Pattern detected: {len(pattern.insight_data['patterns'])} patterns")

    async def test_generate_pattern_content_length(self, db_session):
        """Test pattern detection for content length."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create items with varying content lengths
        for i in range(5):
            content = "x" * (i * 50 + 100)  # 100, 150, 200, 250, 300 chars
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content=content,
                tags=["length"]
            )

        insight_service = InsightService(db_session)
        pattern = await insight_service.generate_pattern(
            item_type="card",
            pattern_type="content_length"
        )

        assert pattern.insight_data["pattern_type"] == "content_length"
        # Find the content_length pattern
        content_pattern = None
        for p in pattern.insight_data["patterns"]:
            if p.get("pattern_name") == "average_content_length":
                content_pattern = p
                break

        assert content_pattern is not None
        assert "value" in content_pattern
        assert content_pattern["value"] > 0
        print(f"✅ Content length pattern: avg={content_pattern['value']:.0f} chars")

    async def test_get_insight(self, db_session):
        """Test retrieving an insight by ID."""
        insight_service = InsightService(db_session)
        search_service = SearchService(db_session, auto_embed=False)

        # First create some card items
        for i in range(5):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Test Card {i}",
                content=f"Test content {i}",
                tags=["test_get_insight"]
            )

        # Create an insight
        summary = await insight_service.generate_summary(
            item_type="card",
            name="Get Test"
        )

        # Retrieve it
        retrieved = await insight_service.get_insight(str(summary.id))

        assert retrieved is not None
        assert retrieved.id == summary.id
        assert retrieved.name == "Get Test"
        print(f"✅ Retrieved insight: {retrieved.name}")

    async def test_list_insights(self, db_session):
        """Test listing insights."""
        insight_service = InsightService(db_session)
        search_service = SearchService(db_session, auto_embed=False)

        # Create some card items first
        for i in range(10):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content=f"Content {i}",
                tags=["test_list"]
            )
        for i in range(5):
            await search_service.index_item(
                item_type="task",
                item_id=uuid.uuid4(),
                title=f"Task {i}",
                content=f"Task content {i}",
                tags=["test_list"]
            )

        # Create multiple insights
        await insight_service.generate_summary(item_type="card", name="Summary 1")
        await insight_service.generate_summary(item_type="task", name="Summary 2")
        await insight_service.generate_trend(item_type="card", group_by="day")

        # List all
        all_insights = await insight_service.list_insights(limit=10)

        assert len(all_insights) >= 3
        print(f"✅ Listed {len(all_insights)} insights")

        # Filter by type
        summaries = await insight_service.list_insights(cluster_type="summary", limit=10)

        assert len(summaries) >= 2
        assert all(i.cluster_type == "summary" for i in summaries)
        print(f"✅ Listed {len(summaries)} summaries")

    async def test_delete_insight(self, db_session):
        """Test deleting an insight."""
        insight_service = InsightService(db_session)
        search_service = SearchService(db_session, auto_embed=False)

        # First create some card items
        for i in range(5):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content=f"Content {i}",
                tags=["test_delete"]
            )

        # Create an insight
        summary = await insight_service.generate_summary(
            item_type="card",
            name="Delete Test"
        )

        # Delete it
        result = await insight_service.delete_insight(str(summary.id))

        assert result is True

        # Verify it's gone
        retrieved = await insight_service.get_insight(str(summary.id))
        assert retrieved is None
        print(f"✅ Insight deleted successfully")

    async def test_delete_nonexistent_insight(self, db_session):
        """Test deleting a non-existent insight."""
        insight_service = InsightService(db_session)

        fake_id = uuid.uuid4()
        result = await insight_service.delete_insight(str(fake_id))

        assert result is False
        print(f"✅ Non-existent insight delete handled correctly")

    async def test_generate_summary_empty_dataset(self, db_session):
        """Test summary generation with no matching data."""
        insight_service = InsightService(db_session)

        # Try to generate summary for an item_type that doesn't exist
        with pytest.raises(ValueError, match="No.*items found matching the criteria"):
            await insight_service.generate_summary(item_type="nonexistent_type")

        print(f"✅ Empty dataset error handled correctly")

    async def test_generate_trend_invalid_group_by(self, db_session):
        """Test trend generation with invalid group_by parameter."""
        insight_service = InsightService(db_session)

        with pytest.raises(ValueError, match="Invalid group_by"):
            await insight_service.generate_trend(
                item_type="card",
                group_by="invalid"
            )

        print(f"✅ Invalid group_by parameter handled correctly")

    async def test_insight_confidence_scores(self, db_session):
        """Test that insights have appropriate confidence scores."""
        search_service = SearchService(db_session, auto_embed=False)

        # Create test data
        for i in range(10):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content="Content",
                tags=["confidence"]
            )

        insight_service = InsightService(db_session)

        # Summary typically has confidence around 0.8
        summary = await insight_service.generate_summary(item_type="card")
        assert summary.confidence is not None
        assert 0.0 <= summary.confidence <= 1.0

        # Trend typically has higher confidence (~0.9)
        trend = await insight_service.generate_trend(
            item_type="card",
            group_by="day"
        )
        assert trend.confidence is not None
        assert 0.0 <= trend.confidence <= 1.0

        # Topics typically have lower confidence (~0.75)
        topics = await insight_service.generate_topics(item_type="card")
        assert topics.confidence is not None
        assert 0.0 <= topics.confidence <= 1.0

        print(f"✅ Confidence scores: summary={summary.confidence}, trend={trend.confidence}, topics={topics.confidence}")


@pytest.mark.asyncio
class TestInsightDataModels:
    """Test insight data model structures."""

    async def test_summary_insight_data_structure(self, db_session):
        """Test that summary insight has correct data structure."""
        search_service = SearchService(db_session, auto_embed=False)

        for i in range(3):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content=f"Content with some text {i}",
                tags=["test", f"tag{i}"]
            )

        insight_service = InsightService(db_session)
        summary = await insight_service.generate_summary(item_type="card")

        # Required fields
        assert "total_items" in summary.insight_data
        assert "summary_text" in summary.insight_data
        assert "key_topics" in summary.insight_data
        assert isinstance(summary.insight_data["key_topics"], list)

        # Optional fields
        if "unique_tags_count" in summary.insight_data:
            assert isinstance(summary.insight_data["unique_tags_count"], int)

        print(f"✅ Summary data structure valid")

    async def test_trend_insight_data_structure(self, db_session):
        """Test that trend insight has correct data structure."""
        search_service = SearchService(db_session, auto_embed=False)

        for i in range(5):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content="Content",
                tags=["trend"]
            )

        insight_service = InsightService(db_session)
        trend = await insight_service.generate_trend(
            item_type="card",
            group_by="day"
        )

        # Required fields
        assert "metric" in trend.insight_data
        assert "group_by" in trend.insight_data
        assert "values" in trend.insight_data
        assert "labels" in trend.insight_data
        assert "trend_direction" in trend.insight_data

        assert isinstance(trend.insight_data["values"], list)
        assert isinstance(trend.insight_data["labels"], list)
        assert trend.insight_data["trend_direction"] in ["up", "down", "stable", "unknown"]

        print(f"✅ Trend data structure valid")

    async def test_topic_insight_data_structure(self, db_session):
        """Test that topic insight has correct data structure."""
        search_service = SearchService(db_session, auto_embed=False)

        for i in range(5):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content="Content",
                tags=[f"topic{i}", "shared"]
            )

        insight_service = InsightService(db_session)
        topics = await insight_service.generate_topics(item_type="card", num_topics=3)

        # Required fields
        assert "num_topics" in topics.insight_data
        assert "topics" in topics.insight_data
        assert "total_items_analyzed" in topics.insight_data

        assert isinstance(topics.insight_data["topics"], list)
        assert len(topics.insight_data["topics"]) <= 3

        # Each topic should have required fields
        for topic in topics.insight_data["topics"]:
            assert "topic_name" in topic
            assert "frequency" in topic
            assert "percentage" in topic

        print(f"✅ Topic data structure valid")

    async def test_pattern_insight_data_structure(self, db_session):
        """Test that pattern insight has correct data structure."""
        search_service = SearchService(db_session, auto_embed=False)

        for i in range(3):
            await search_service.index_item(
                item_type="card",
                item_id=uuid.uuid4(),
                title=f"Card {i}",
                content="Content",
                tags=["pattern"]
            )

        insight_service = InsightService(db_session)
        pattern = await insight_service.generate_pattern(
            item_type="card",
            pattern_type="creation_time"
        )

        # Required fields
        assert "pattern_type" in pattern.insight_data
        assert "patterns" in pattern.insight_data
        assert "total_items_analyzed" in pattern.insight_data

        assert isinstance(pattern.insight_data["patterns"], list)

        print(f"✅ Pattern data structure valid")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
