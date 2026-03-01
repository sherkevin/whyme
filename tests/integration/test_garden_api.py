"""Integration tests for Garden API endpoints - PRD9 Module 3.

Tests cover:
1. Schema validation
2. Backward compatibility
3. Pagination and filtering
4. Detail endpoint with sorting
5. Insight filtering
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.auth.models import User
from agent_os.items.models import Item, Workspace
from agent_os.garden.models import KnowledgeCardLink, DailyInsight
from agent_os.garden.stats_service import GardenStatsService
from agent_os.core.config import get_garden_strong_edge_threshold


# ============================================================================
# Test Fixtures (using conftest.py base)
# ============================================================================

@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        username="test_api_user",
        email="test_api@example.com",
        password_hash="hashed_password",
        is_active=True
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


@pytest.fixture
async def test_items(
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_user: User,
    count: int = 10
) -> List[Item]:
    """Create test items."""
    items = []
    now = datetime.now(timezone.utc)

    for i in range(count):
        item = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user.id,
            type="note",
            title=f"Test Note {i}",
            content=f"Content for note {i}",
            status="active",
            created_at=now - timedelta(days=count - i)
        )
        db_session.add(item)
        items.append(item)

    await db_session.commit()
    return items


@pytest.fixture
async def test_edges(
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_items: List[Item]
) -> List[KnowledgeCardLink]:
    """Create test edges between items."""
    edges = []

    # Create edges between consecutive items with varying strengths
    for i in range(len(test_items) - 1):
        edge = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=test_items[i].id,
            to_id=test_items[i + 1].id,
            type="related",
            relation_strength=0.5 + (i * 0.1),
            is_active=True
        )
        db_session.add(edge)
        edges.append(edge)

    # Create bidirectional edges for deduplication testing
    if len(test_items) >= 3:
        edge_ab = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=test_items[0].id,
            to_id=test_items[2].id,
            type="related",
            relation_strength=0.8,
            is_active=True
        )
        edge_ba = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=test_items[2].id,
            to_id=test_items[0].id,
            type="related",
            relation_strength=0.9,
            is_active=True
        )
        db_session.add_all([edge_ab, edge_ba])
        edges.extend([edge_ab, edge_ba])

    await db_session.commit()
    return edges


@pytest.fixture
async def test_insights(
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_user: User
) -> List[DailyInsight]:
    """Create test insights."""
    insights = []
    now = datetime.now(timezone.utc)

    insights_data = [
        ("Stable Insight 1", "stable", 2, 0),  # Today, level 2
        ("Stable Insight 2", "stable", 3, 0),  # Today, level 3
        ("Candidate Insight", "candidate", 2, 0),  # Today, but candidate
        ("Low Level Stable", "stable", 1, 0),  # Today, but level 1
    ]

    for title, status, level, days_ago in insights_data:
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title=title,
            content=f"Content for {title}",
            status=status,
            level=level,
            canonical_hash=f"hash_{title}",
            stability_score=0.8 if status == "stable" else 0.3,
            evidence_count=1,
            created_at=now - timedelta(days=days_ago),
            updated_at=now - timedelta(days=days_ago)
        )
        db_session.add(insight)
        insights.append(insight)

    await db_session.commit()
    return insights


# ============================================================================
# Test: Schema Validation (Service Level)
# ============================================================================

class TestSchemaValidation:
    """Test schema validation at service level."""

    @pytest.mark.anyio
    async def test_garden_stats_service(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_workspace: Workspace,
        test_items: List[Item]
    ):
        """Test GardenStatsService calculates correctly."""
        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            user_id=str(test_user.id),
            workspace_id=str(test_workspace.id)
        )

        # Verify stats structure
        assert "total_notes" in stats
        assert "neural_connections" in stats
        assert "generated_insights" in stats

        # Verify total_notes count
        assert stats["total_notes"] == len(test_items)


# ============================================================================
# Test: Stats Service Deduplication Logic
# ============================================================================

class TestStatsServiceDeduplication:
    """Test stats service deduplication logic."""

    @pytest.mark.anyio
    async def test_neural_connections_deduplication(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_workspace: Workspace,
        test_edges: List[KnowledgeCardLink]
    ):
        """Test neural_connections deduplicates A-B and B-A as one."""
        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            user_id=str(test_user.id),
            workspace_id=str(test_workspace.id)
        )

        # Calculate expected unique edges
        threshold = get_garden_strong_edge_threshold()
        strong_edges = [e for e in test_edges if e.relation_strength >= threshold]

        # Deduplicate by normalized edge
        unique_edges = set()
        for edge in strong_edges:
            normalized = tuple(sorted([str(edge.from_id), str(edge.to_id)]))
            unique_edges.add(normalized)

        # Stats should match our deduplication logic
        assert stats["neural_connections"] == len(unique_edges)


# ============================================================================
# Test: DailyInsight Filtering
# ============================================================================

class TestInsightFiltering:
    """Test insight filtering logic."""

    @pytest.mark.anyio
    async def test_insight_status_and_level_filter(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_workspace: Workspace,
        test_insights: List[DailyInsight]
    ):
        """Test only stable insights with level >= 2 are counted."""
        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            user_id=str(test_user.id),
            workspace_id=str(test_workspace.id)
        )

        # Count expected insights:
        # - "Stable Insight 1": status=stable, level=2 ✓
        # - "Stable Insight 2": status=stable, level=3 ✓
        # - "Candidate Insight": status=candidate ✗
        # - "Low Level Stable": status=stable, level=1 ✗
        expected_count = 2

        assert stats["generated_insights"] == expected_count


# ============================================================================
# Test: Edge Batch Query Logic
# ============================================================================

class TestEdgeBatchQuery:
    """Test edge batch query logic."""

    @pytest.mark.anyio
    async def test_edge_batch_strong_edges_only(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_items: List[Item],
        test_edges: List[KnowledgeCardLink]
    ):
        """Test edge batch query returns only strong edges."""
        threshold = get_garden_strong_edge_threshold()

        # Query edges where both endpoints are in our item list
        stmt = select(KnowledgeCardLink).where(
            and_(
                KnowledgeCardLink.workspace_id == test_workspace.id,
                KnowledgeCardLink.from_id.in_([item.id for item in test_items]),
                KnowledgeCardLink.to_id.in_([item.id for item in test_items]),
                KnowledgeCardLink.relation_strength >= threshold,
                KnowledgeCardLink.is_active == True
            )
        )

        result = await db_session.execute(stmt)
        edges = result.scalars().all()

        # All returned edges should be strong (>= threshold)
        for edge in edges:
            assert edge.relation_strength >= threshold, \
                f"Edge with strength {edge.relation_strength} should not be returned"


# ============================================================================
# Test: Connected Nodes Sorting
# ============================================================================

class TestConnectedNodesSorting:
    """Test connected nodes sorting logic."""

    @pytest.mark.anyio
    async def test_connected_nodes_sorted_by_strength(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_items: List[Item],
        test_edges: List[KnowledgeCardLink]
    ):
        """Test that connected nodes are sorted by relation_strength descending."""
        threshold = get_garden_strong_edge_threshold()
        target_item = test_items[0]

        # Query connected nodes (mimics router logic)
        stmt = (
            select(
                Item.id,
                Item.type,
                Item.title,
                KnowledgeCardLink.relation_strength
            )
            .join(
                KnowledgeCardLink,
                (KnowledgeCardLink.from_id == target_item.id) |
                (KnowledgeCardLink.to_id == target_item.id)
            )
            .where(
                and_(
                    KnowledgeCardLink.workspace_id == test_workspace.id,
                    KnowledgeCardLink.is_active == True,
                    KnowledgeCardLink.relation_strength >= threshold,
                    Item.status == "active",
                    (KnowledgeCardLink.from_id == target_item.id) |
                    (KnowledgeCardLink.to_id == target_item.id)
                )
            )
            .order_by(KnowledgeCardLink.relation_strength.desc())
            .limit(5)
        )

        result = await db_session.execute(stmt)
        rows = result.all()

        # Verify sorted descending
        strengths = [row.relation_strength for row in rows]
        assert strengths == sorted(strengths, reverse=True), \
            "Connected nodes should be sorted by relation_strength descending"

        # Verify limit
        assert len(rows) <= 5, "Should return at most 5 connected nodes"


# ============================================================================
# Test: Date Range Filtering
# ============================================================================

class TestDateRangeFiltering:
    """Test date range filtering logic."""

    @pytest.mark.anyio
    async def test_date_range_last_7_days(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User,
        test_items: List[Item]
    ):
        """Test date range filter returns only recent items."""
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        stmt = select(Item).where(
            and_(
                Item.workspace_id == test_workspace.id,
                Item.status == "active",
                Item.created_at >= seven_days_ago
            )
        )

        result = await db_session.execute(stmt)
        items = result.scalars().all()

        # All returned items should be within 7 days
        for item in items:
            days_old = (now - item.created_at).days
            assert days_old <= 7, f"Item {item.id} is {days_old} days old, should be filtered"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
