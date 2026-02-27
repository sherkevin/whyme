"""Tests for Cluster Service and Insight Worker.

Tests:
- cluster_strength formula calculation
- Insight trigger conditions (sources >= 3, timespan >= 3 days, cluster_strength >= 2.5)
- Status transition (candidate -> stable)
- Deduplication by canonical_hash (evidence_count increment)
"""

import pytest
import uuid
import json
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from agent_os.garden.cluster_service import ClusterService, InsightWorker
from agent_os.garden.models import KnowledgeCardLink, DailyInsight
from agent_os.items.models import Item, Workspace
from agent_os.auth.models import User


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        username="test_user",
        email="test@example.com",
        password_hash="hashed_password"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_workspace(db_session: AsyncSession, test_user: User) -> Workspace:
    """Create a test workspace."""
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Workspace",
        owner_id=test_user.id
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


class TestClusterService:
    """Test Cluster Service strength calculation."""

    async def test_cluster_strength_formula(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test cluster_strength formula calculation.

        Formula: cluster_strength = strong_edges_count + (avg_relation_strength * 2.0) + (1.0 / (avg_days_between_nodes + 1))
        """
        # Create 3 items with known dates
        base_date = datetime(2026, 1, 1)
        items = []
        for i in range(3):
            item = Item(
                workspace_id=test_workspace.id,
                creator_id=test_user.id,
                type="note",
                title=f"Item {i}",
                content=f"Content {i}",
                status="active",
                created_at=base_date + timedelta(days=i * 3)  # 0, 3, 6 days apart
            )
            db_session.add(item)
            items.append(item)
        await db_session.commit()

        # Create edges with known strengths
        # 2 strong edges (>= 0.65 threshold)
        edges = [
            KnowledgeCardLink(
                workspace_id=test_workspace.id,
                from_id=items[0].id,
                to_id=items[1].id,
                type="related",
                relation_strength=0.8,  # Strong
                is_active=True,
                created_at=base_date + timedelta(days=1)
            ),
            KnowledgeCardLink(
                workspace_id=test_workspace.id,
                from_id=items[1].id,
                to_id=items[2].id,
                type="related",
                relation_strength=0.9,  # Strong
                is_active=True,
                created_at=base_date + timedelta(days=4)
            ),
        ]
        db_session.add_all(edges)
        await db_session.commit()

        service = ClusterService(db_session)
        node_ids = [str(item.id) for item in items]
        cluster_strength = await service.compute_cluster_strength(
            node_ids, str(test_workspace.id)
        )

        # Calculate expected values:
        # strong_edges_count = 2 (both edges are strong)
        # avg_relation_strength = (0.8 + 0.9) / 2 = 0.85
        # avg_days_between_nodes = 3 days (edges created 3 days apart)
        # cluster_strength = 2 + (0.85 * 2.0) + (1.0 / (3 + 1))
        #                  = 2 + 1.7 + 0.25 = 3.95

        assert cluster_strength == pytest.approx(3.95, rel=0.1)

    async def test_cluster_strength_no_edges(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test cluster_strength returns 0 when no edges exist."""
        # Create items without edges
        item = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user.id,
            type="note",
            title="Isolated Item",
            status="active"
        )
        db_session.add(item)
        await db_session.commit()

        service = ClusterService(db_session)
        cluster_strength = await service.compute_cluster_strength(
            [str(item.id)], str(test_workspace.id)
        )

        # Single node returns base strength
        assert cluster_strength == pytest.approx(0.5, rel=0.1)

    async def test_cluster_strength_weak_edges_only(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test cluster_strength with only weak edges."""
        # Create items
        item_a = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user.id,
            type="note",
            title="Item A",
            status="active"
        )
        item_b = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user.id,
            type="note",
            title="Item B",
            status="active"
        )
        db_session.add_all([item_a, item_b])
        await db_session.commit()

        # Create weak edge (below threshold)
        edge = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item_a.id,
            to_id=item_b.id,
            type="related",
            relation_strength=0.3,  # Weak
            is_active=True
        )
        db_session.add(edge)
        await db_session.commit()

        service = ClusterService(db_session)
        node_ids = [str(item_a.id), str(item_b.id)]
        cluster_strength = await service.compute_cluster_strength(
            node_ids, str(test_workspace.id)
        )

        # strong_edges_count = 0
        # avg_relation_strength = 0.3
        # cluster_strength = 0 + (0.3 * 2.0) + (1.0 / (0 + 1))
        #                  = 0 + 0.6 + 1.0 = 1.6
        assert cluster_strength == pytest.approx(1.6, rel=0.1)


class TestInsightWorker:
    """Test Insight Worker status transitions and deduplication."""

    async def test_trigger_conditions_met_transitions_to_stable(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test insight transitions to stable when all conditions are met."""
        # Create 3 source items with sufficient timespan
        base_date = datetime(2026, 1, 1)
        items = []
        for i in range(3):
            item = Item(
                workspace_id=test_workspace.id,
                creator_id=test_user.id,
                type="note",
                title=f"Source {i}",
                content=f"Content {i}",
                status="active",
                created_at=base_date + timedelta(days=i * 2)  # 0, 2, 4 days - timespan = 4 days
            )
            db_session.add(item)
            items.append(item)
        await db_session.commit()

        # Create strong edges between items for cluster strength
        edges = [
            KnowledgeCardLink(
                workspace_id=test_workspace.id,
                from_id=items[0].id,
                to_id=items[1].id,
                type="related",
                relation_strength=0.9,
                is_active=True
            ),
            KnowledgeCardLink(
                workspace_id=test_workspace.id,
                from_id=items[1].id,
                to_id=items[2].id,
                type="related",
                relation_strength=0.9,
                is_active=True
            ),
            KnowledgeCardLink(
                workspace_id=test_workspace.id,
                from_id=items[0].id,
                to_id=items[2].id,
                type="related",
                relation_strength=0.9,
                is_active=True
            ),
        ]
        db_session.add_all(edges)
        await db_session.commit()

        # Create candidate insight
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title="Test Insight",
            content="Content",
            status="candidate",
            level=2,
            canonical_hash="test_hash",
            stability_score=0.0,
            evidence_count=1
        )
        db_session.add(insight)
        await db_session.commit()

        # Process insight
        worker = InsightWorker(db_session)
        source_ids = [str(item.id) for item in items]
        result = await worker.process_candidate_insight(
            str(insight.id), source_ids, str(test_workspace.id)
        )

        # Verify transition to stable
        assert result["success"] is True
        assert result["status"] == "stable"

        # Verify insight was updated in DB
        await db_session.refresh(insight)
        assert insight.status == "stable"

    async def test_trigger_conditions_not_met_sources(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test insight does NOT transition when sources < 3."""
        # Create only 2 source items (less than required 3)
        items = []
        for i in range(2):
            item = Item(
                workspace_id=test_workspace.id,
                creator_id=test_user.id,
                type="note",
                title=f"Source {i}",
                status="active"
            )
            db_session.add(item)
            items.append(item)
        await db_session.commit()

        # Create candidate insight
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title="Test Insight",
            content="Content",
            status="candidate",
            level=2,
            canonical_hash="test_hash",
            evidence_count=1
        )
        db_session.add(insight)
        await db_session.commit()

        worker = InsightWorker(db_session)
        source_ids = [str(item.id) for item in items]
        result = await worker.process_candidate_insight(
            str(insight.id), source_ids, str(test_workspace.id)
        )

        # Verify NOT transitioned
        assert result["success"] is False
        assert result["status"] == "candidate"
        assert "Insufficient sources" in result["reason"]

        # Verify insight status unchanged
        await db_session.refresh(insight)
        assert insight.status == "candidate"

    async def test_trigger_conditions_not_met_timespan(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test insight does NOT transition when timespan < 3 days."""
        # Create 3 items but all on same day (timespan < 3 days)
        base_date = datetime(2026, 1, 1)
        items = []
        for i in range(3):
            item = Item(
                workspace_id=test_workspace.id,
                creator_id=test_user.id,
                type="note",
                title=f"Source {i}",
                status="active",
                created_at=base_date + timedelta(hours=i)  # Same day
            )
            db_session.add(item)
            items.append(item)
        await db_session.commit()

        # Create candidate insight
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title="Test Insight",
            content="Content",
            status="candidate",
            level=2,
            canonical_hash="test_hash",
            evidence_count=1
        )
        db_session.add(insight)
        await db_session.commit()

        worker = InsightWorker(db_session)
        source_ids = [str(item.id) for item in items]
        result = await worker.process_candidate_insight(
            str(insight.id), source_ids, str(test_workspace.id)
        )

        # Verify NOT transitioned
        assert result["success"] is False
        assert "Insufficient timespan" in result["reason"]

    async def test_deduplication_evidence_count_increment(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test deduplication increments evidence_count instead of creating new record."""
        # Create source items
        items = []
        for i in range(2):
            item = Item(
                workspace_id=test_workspace.id,
                creator_id=test_user.id,
                type="note",
                title=f"Source {i}",
                status="active"
            )
            db_session.add(item)
            items.append(item)
        await db_session.commit()

        worker = InsightWorker(db_session)
        source_ids = [str(item.id) for item in items]

        # First upsert - should create new record
        result1 = await worker.upsert_insight_with_deduplication(
            workspace_id=str(test_workspace.id),
            user_id=str(test_user.id),
            canonical_hash="same_hash",
            title="Test Insight",
            content="Content",
            source_item_ids=source_ids,
            level=2
        )

        assert result1["action"] == "created"
        assert result1["evidence_count"] == 1
        first_insight_id = result1["insight_id"]

        # Second upsert with same canonical_hash - should update, not create
        new_item = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user.id,
            type="note",
            title="New Source",
            status="active"
        )
        db_session.add(new_item)
        await db_session.commit()

        result2 = await worker.upsert_insight_with_deduplication(
            workspace_id=str(test_workspace.id),
            user_id=str(test_user.id),
            canonical_hash="same_hash",  # Same hash
            title="Test Insight Updated",
            content="Updated Content",
            source_item_ids=[str(new_item.id)],
            level=2
        )

        assert result2["action"] == "updated"
        assert result2["evidence_count"] == 2
        assert result2["insight_id"] == first_insight_id  # Same record

        # Verify only ONE insight record exists
        from sqlalchemy import select, func
        stmt = select(func.count(DailyInsight.id)).where(
            DailyInsight.canonical_hash == "same_hash"
        )
        count_result = await db_session.execute(stmt)
        count = count_result.scalar()
        assert count == 1

    async def test_deduplication_source_ids_merged(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test deduplication merges source_item_ids."""
        # Create source items
        items_batch1 = []
        for i in range(2):
            item = Item(
                workspace_id=test_workspace.id,
                creator_id=test_user.id,
                type="note",
                title=f"Source {i}",
                status="active"
            )
            db_session.add(item)
            items_batch1.append(item)
        await db_session.commit()

        worker = InsightWorker(db_session)

        # First upsert
        result1 = await worker.upsert_insight_with_deduplication(
            workspace_id=str(test_workspace.id),
            user_id=str(test_user.id),
            canonical_hash="merge_test_hash",
            title="Test",
            content="Content",
            source_item_ids=[str(item.id) for item in items_batch1],
            level=2
        )

        # Second upsert with different sources
        items_batch2 = []
        for i in range(2):
            item = Item(
                workspace_id=test_workspace.id,
                creator_id=test_user.id,
                type="note",
                title=f"New Source {i}",
                status="active"
            )
            db_session.add(item)
            items_batch2.append(item)
        await db_session.commit()

        result2 = await worker.upsert_insight_with_deduplication(
            workspace_id=str(test_workspace.id),
            user_id=str(test_user.id),
            canonical_hash="merge_test_hash",
            title="Test",
            content="Content",
            source_item_ids=[str(item.id) for item in items_batch2],
            level=2
        )

        # Verify sources were merged
        insight_id = result2["insight_id"]
        stmt = select(DailyInsight).where(DailyInsight.id == uuid.UUID(insight_id))
        result = await db_session.execute(stmt)
        insight = result.scalar_one_or_none()

        assert insight is not None
        merged_sources = json.loads(insight.source_item_ids)

        # Should contain all 4 unique source IDs
        expected_ids = set(str(item.id) for item in items_batch1 + items_batch2)
        assert set(merged_sources) == expected_ids

    async def test_compute_canonical_hash(self):
        """Test canonical hash computation."""
        worker = InsightWorker(None)  # No DB session needed for static method

        content = "Test content for hashing"
        hash1 = worker.compute_canonical_hash(content)
        hash2 = worker.compute_canonical_hash(content)
        hash3 = worker.compute_canonical_hash("Different content")

        # Same content produces same hash
        assert hash1 == hash2

        # Different content produces different hash
        assert hash1 != hash3

        # Hash is 64 characters (SHA-256 hex)
        assert len(hash1) == 64
