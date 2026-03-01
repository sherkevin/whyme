"""Tests for Garden Stats Service.

Tests:
- total_notes: Count of active notes/cards
- neural_connections: Undirected graph deduplication (A-B and B-A count as 1)
- generated_insights: Stable insights with level >= 2, deduplicated by canonical_hash
"""

import pytest
import uuid
from datetime import datetime
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.garden.stats_service import GardenStatsService
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


@pytest.fixture
async def test_items(
    db_session: AsyncSession,
    test_workspace: Workspace,
    test_user: User,
    count: int = 5
) -> List[Item]:
    """Create test items."""
    items = []
    for i in range(count):
        item = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user.id,
            type="note",
            title=f"Test Note {i}",
            content=f"Content {i}",
            status="active"
        )
        db_session.add(item)
        items.append(item)
    await db_session.commit()
    return items


class TestGardenStatsService:
    """Test Garden Stats Service."""

    async def test_total_notes_count(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User,
        test_items: List[Item]
    ):
        """Test total_notes counts active items correctly."""
        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            str(test_user.id),
            str(test_workspace.id)
        )
        assert stats["total_notes"] == 5

    async def test_total_notes_excludes_inactive(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test total_notes excludes inactive items."""
        # Create mixed status items
        active_item = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user.id,
            type="note",
            title="Active",
            status="active"
        )
        archived_item = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user.id,
            type="note",
            title="Archived",
            status="archived"
        )
        db_session.add_all([active_item, archived_item])
        await db_session.commit()

        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            str(test_user.id),
            str(test_workspace.id)
        )
        assert stats["total_notes"] == 1  # Only active counted

    async def test_neural_connections_deduplication(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test neural_connections deduplicates A-B and B-A as one connection."""
        # Create items for edges
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

        # Create bidirectional strong edges (A->B and B->A)
        edge_ab = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item_a.id,
            to_id=item_b.id,
            type="related",
            relation_strength=0.8,  # Above default threshold 0.65
            is_active=True
        )
        edge_ba = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item_b.id,
            to_id=item_a.id,
            type="related",
            relation_strength=0.9,  # Above threshold
            is_active=True
        )
        db_session.add_all([edge_ab, edge_ba])
        await db_session.commit()

        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            str(test_user.id),
            str(test_workspace.id)
        )

        # A-B and B-A should count as ONE connection
        assert stats["neural_connections"] == 1

    async def test_neural_connections_weak_edges_excluded(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test neural_connections excludes weak edges below threshold."""
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
        item_c = Item(
            workspace_id=test_workspace.id,
            creator_id=test_user.id,
            type="note",
            title="Item C",
            status="active"
        )
        db_session.add_all([item_a, item_b, item_c])
        await db_session.commit()

        # Create one strong edge and one weak edge
        strong_edge = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item_a.id,
            to_id=item_b.id,
            type="related",
            relation_strength=0.8,  # Above threshold
            is_active=True
        )
        weak_edge = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item_b.id,
            to_id=item_c.id,
            type="related",
            relation_strength=0.5,  # Below threshold 0.65
            is_active=True
        )
        db_session.add_all([strong_edge, weak_edge])
        await db_session.commit()

        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            str(test_user.id),
            str(test_workspace.id)
        )

        # Only strong edge counted
        assert stats["neural_connections"] == 1

    async def test_neural_connections_inactive_excluded(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test neural_connections excludes inactive edges."""
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

        # Create active and inactive strong edges
        active_edge = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item_a.id,
            to_id=item_b.id,
            type="related",
            relation_strength=0.8,
            is_active=True
        )
        inactive_edge = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item_b.id,
            to_id=item_a.id,
            type="related",
            relation_strength=0.9,
            is_active=False  # Inactive
        )
        db_session.add_all([active_edge, inactive_edge])
        await db_session.commit()

        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            str(test_user.id),
            str(test_workspace.id)
        )

        # Only active edge counted
        assert stats["neural_connections"] == 1

    async def test_generated_insights_level_filter(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test generated_insights only counts level >= 2 stable insights."""
        # Create insights with different levels and statuses
        insights = [
            DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title="Level 1 Stable",
                content="Content",
                status="stable",
                level=1,  # Should NOT count
                canonical_hash="hash1",
                stability_score=0.5,
                evidence_count=1
            ),
            DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title="Level 2 Stable",
                content="Content",
                status="stable",
                level=2,  # Should count
                canonical_hash="hash2",
                stability_score=0.6,
                evidence_count=1
            ),
            DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title="Level 3 Stable",
                content="Content",
                status="stable",
                level=3,  # Should count
                canonical_hash="hash3",
                stability_score=0.7,
                evidence_count=1
            ),
            DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title="Level 2 Candidate",
                content="Content",
                status="candidate",  # Should NOT count
                level=2,
                canonical_hash="hash4",
                stability_score=0.0,
                evidence_count=1
            ),
        ]
        db_session.add_all(insights)
        await db_session.commit()

        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            str(test_user.id),
            str(test_workspace.id)
        )

        # Only level 2 and 3 stable insights counted
        assert stats["generated_insights"] == 2

    async def test_generated_insights_canonical_hash_deduplication(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test generated_insights deduplicates by canonical_hash."""
        # Create insights with same canonical_hash
        insights = [
            DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title="Duplicate 1",
                content="Content 1",
                status="stable",
                level=2,
                canonical_hash="same_hash",  # Same hash
                stability_score=0.5,
                evidence_count=1
            ),
            DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title="Duplicate 2",
                content="Content 2",
                status="stable",
                level=2,
                canonical_hash="same_hash",  # Same hash - should NOT count again
                stability_score=0.6,
                evidence_count=1
            ),
            DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title="Unique",
                content="Content 3",
                status="stable",
                level=2,
                canonical_hash="different_hash",  # Different hash - should count
                stability_score=0.7,
                evidence_count=1
            ),
        ]
        db_session.add_all(insights)
        await db_session.commit()

        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            str(test_user.id),
            str(test_workspace.id)
        )

        # Deduplicated: same_hash counts once, different_hash counts once
        assert stats["generated_insights"] == 2

    async def test_generated_insights_null_hash_excluded(
        self,
        db_session: AsyncSession,
        test_workspace: Workspace,
        test_user: User
    ):
        """Test insights with null canonical_hash are excluded."""
        insights = [
            DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title="No Hash",
                content="Content",
                status="stable",
                level=2,
                canonical_hash=None,  # Null hash - should NOT count
                stability_score=0.5,
                evidence_count=1
            ),
            DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title="With Hash",
                content="Content",
                status="stable",
                level=2,
                canonical_hash="valid_hash",
                stability_score=0.6,
                evidence_count=1
            ),
        ]
        db_session.add_all(insights)
        await db_session.commit()

        service = GardenStatsService(db_session)
        stats = await service.get_user_garden_stats(
            str(test_user.id),
            str(test_workspace.id)
        )

        # Only insight with valid hash counted
        assert stats["generated_insights"] == 1
