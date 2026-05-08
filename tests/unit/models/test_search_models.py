"""Unit tests for Stage 4 data models."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from agent_os.search_engine.models import IngestionJob, InsightCluster, SearchIndex


@pytest.mark.asyncio
class TestSearchIndexModel:
    """Test SearchIndex model."""

    async def test_create_search_index(self, db_session):
        """Test creating a search index entry."""
        item_id = uuid.uuid4()

        index = SearchIndex(
            item_type="card",
            item_id=item_id,
            title="Test Card",
            content="Test content here",
            tags=["test", "example"],
            search_metadata={"workspace_id": str(uuid.uuid4())}
        )

        db_session.add(index)
        await db_session.commit()
        await db_session.refresh(index)

        assert index.id is not None
        assert index.item_type == "card"
        assert index.item_id == item_id
        assert index.title == "Test Card"
        assert len(index.tags) == 2
        print(f"✅ Created SearchIndex: {index.item_type}:{index.item_id}")

    async def test_search_index_defaults(self, db_session):
        """Test default values."""
        index = SearchIndex(
            item_type="task",
            item_id=uuid.uuid4(),
            title="Test Task"
        )

        db_session.add(index)
        await db_session.commit()
        await db_session.refresh(index)

        assert index.tags == []
        assert index.search_metadata == {}
        assert index.embedding is None
        assert index.created_at is not None
        print("✅ Default values verified for SearchIndex")

    async def test_search_index_with_embedding(self, db_session):
        """Test search index with vector embedding."""
        index = SearchIndex(
            item_type="note",
            item_id=uuid.uuid4(),
            title="Note with embedding",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5]
        )

        db_session.add(index)
        await db_session.commit()
        await db_session.refresh(index)

        assert index.embedding is not None
        assert len(index.embedding) == 5
        print("✅ SearchIndex with embedding created")


@pytest.mark.asyncio
class TestIngestionJobModel:
    """Test IngestionJob model."""

    async def test_create_ingestion_job_url(self, db_session):
        """Test creating a URL ingestion job."""
        user_id = str(uuid.uuid4())

        job = IngestionJob(
            source_type="url",
            source_url="https://example.com/article",
            chunk_size=1000,
            overlap=200,
            created_by=user_id
        )

        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        assert job.id is not None
        assert job.source_type == "url"
        assert job.source_url == "https://example.com/article"
        assert job.status == "pending"
        assert job.chunk_size == 1000
        assert job.overlap == 200
        print(f"✅ Created URL IngestionJob: {job.id}")

    async def test_create_ingestion_job_pdf(self, db_session):
        """Test creating a PDF ingestion job."""
        job = IngestionJob(
            source_type="pdf",
            source_file_path="/data/document.pdf",
            chunk_size=2000,
            overlap=300
        )

        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        assert job.source_type == "pdf"
        assert job.source_file_path == "/data/document.pdf"
        assert job.status == "pending"
        print(f"✅ Created PDF IngestionJob: {job.id}")

    async def test_ingestion_job_status_transition(self, db_session):
        """Test job status transitions."""
        job = IngestionJob(
            source_type="url",
            source_url="https://example.com"
        )

        db_session.add(job)
        await db_session.commit()

        # Transition to running
        job.status = "running"
        job.started_at = datetime.utcnow()
        await db_session.commit()

        assert job.status == "running"
        assert job.started_at is not None

        # Transition to completed
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.items_created = 5
        job.item_ids = [str(uuid.uuid4()) for _ in range(5)]
        await db_session.commit()

        assert job.status == "completed"
        assert job.completed_at is not None
        assert job.items_created == 5
        assert len(job.item_ids) == 5
        print("✅ Status transition verified: pending -> running -> completed")

    async def test_ingestion_job_error_tracking(self, db_session):
        """Test error tracking in ingestion jobs."""
        job = IngestionJob(
            source_type="url",
            source_url="https://invalid.example"
        )

        db_session.add(job)
        await db_session.commit()

        # Simulate failure
        job.status = "failed"
        job.error_message = "Connection timeout"
        job.error_stack = "Traceback...\nConnectionError"
        job.completed_at = datetime.utcnow()
        await db_session.commit()

        assert job.status == "failed"
        assert job.error_message == "Connection timeout"
        assert job.error_stack is not None
        print("✅ Error tracking verified")


@pytest.mark.asyncio
class TestInsightClusterModel:
    """Test InsightCluster model."""

    async def test_create_summary_insight(self, db_session):
        """Test creating a summary insight cluster."""
        user_id = str(uuid.uuid4())

        insight = InsightCluster(
            cluster_type="summary",
            name="Weekly Summary",
            description="Summary of this week's activities",
            source_item_type="card",
            source_item_ids=[str(uuid.uuid4()) for _ in range(10)],
            date_range={"start": "2026-01-01", "end": "2026-01-07"},
            insight_data={
                "total_items": 10,
                "summary_text": "This week focused on...",
                "key_topics": ["design", "development"],
                "sentiment": "positive"
            },
            confidence=0.85,
            sample_count=10,
            generated_by=user_id
        )

        db_session.add(insight)
        await db_session.commit()
        await db_session.refresh(insight)

        assert insight.id is not None
        assert insight.cluster_type == "summary"
        assert insight.name == "Weekly Summary"
        assert insight.confidence == 0.85
        assert insight.sample_count == 10
        print(f"✅ Created summary InsightCluster: {insight.name}")

    async def test_create_trend_insight(self, db_session):
        """Test creating a trend insight cluster."""
        insight = InsightCluster(
            cluster_type="trend",
            name="Task Completion Trend",
            source_item_type="task",
            insight_data={
                "trend_name": "completion_rate",
                "values": [0.7, 0.75, 0.8, 0.82],
                "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
                "trend_direction": "up"
            },
            confidence=0.9,
            sample_count=200
        )

        db_session.add(insight)
        await db_session.commit()
        await db_session.refresh(insight)

        assert insight.cluster_type == "trend"
        assert insight.insight_data["trend_direction"] == "up"
        assert insight.confidence == 0.9
        print(f"✅ Created trend InsightCluster: {insight.name}")

    async def test_create_topic_insight(self, db_session):
        """Test creating a topic clustering insight."""
        insight = InsightCluster(
            cluster_type="topic",
            name="Topic Clustering",
            description="Main topics in recent cards",
            source_item_type="card",
            insight_data={
                "topics": [
                    {"name": "Product Design", "count": 25, "keywords": ["UI", "UX", "design"]},
                    {"name": "Backend", "count": 18, "keywords": ["API", "database", "server"]},
                    {"name": "Documentation", "count": 12, "keywords": ["docs", "guide", "tutorial"]}
                ]
            },
            confidence=0.75,
            sample_count=55
        )

        db_session.add(insight)
        await db_session.commit()
        await db_session.refresh(insight)

        assert insight.cluster_type == "topic"
        assert len(insight.insight_data["topics"]) == 3
        print(f"✅ Created topic InsightCluster: {insight.name}")

    async def test_insight_expiration(self, db_session):
        """Test insight with expiration date."""
        from datetime import timedelta

        insight = InsightCluster(
            cluster_type="summary",
            name="Expiring Summary",
            source_item_type="card",
            insight_data={"summary": "Test"},
            expires_at=datetime.utcnow() + timedelta(days=7)
        )

        db_session.add(insight)
        await db_session.commit()
        await db_session.refresh(insight)

        assert insight.expires_at is not None
        assert insight.expires_at > datetime.utcnow()
        print("✅ Insight with expiration created")


@pytest.mark.asyncio
class TestModelConstraints:
    """Test model constraints and validations."""

    async def test_search_index_item_type_constraint(self, db_session):
        """Test that only valid item types are allowed."""
        with pytest.raises(IntegrityError) as exc_info:
            index = SearchIndex(
                item_type="invalid_type",  # Invalid type
                item_id=uuid.uuid4(),
                title="Test"
            )
            db_session.add(index)
            await db_session.commit()

        assert "check_search_item_type" in str(exc_info.value)
        print("✅ Item type constraint enforced")

    async def test_ingestion_job_status_constraint(self, db_session):
        """Test that only valid statuses are allowed."""
        with pytest.raises(IntegrityError) as exc_info:
            job = IngestionJob(
                source_type="url",
                status="invalid_status"  # Invalid status
            )
            db_session.add(job)
            await db_session.commit()

        assert "check_ingestion_status" in str(exc_info.value)
        print("✅ Status constraint enforced")

    async def test_ingestion_job_source_type_constraint(self, db_session):
        """Test that only valid source types are allowed."""
        with pytest.raises(IntegrityError) as exc_info:
            job = IngestionJob(
                source_type="invalid_source"  # Invalid source
            )
            db_session.add(job)
            await db_session.commit()

        assert "check_ingestion_source_type" in str(exc_info.value)
        print("✅ Source type constraint enforced")

    async def test_insight_cluster_type_constraint(self, db_session):
        """Test that only valid cluster types are allowed."""
        with pytest.raises(IntegrityError) as exc_info:
            insight = InsightCluster(
                cluster_type="invalid_type",  # Invalid type
                insight_data={}
            )
            db_session.add(insight)
            await db_session.commit()

        assert "check_insight_cluster_type" in str(exc_info.value)
        print("✅ Cluster type constraint enforced")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
