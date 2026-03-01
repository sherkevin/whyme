"""PRD7 Garden Models Tests - Database Model Validation.

This module tests the KnowledgeCardLink and DailyInsight models
to ensure all constraints, defaults, and indexes work correctly.

Tests cover:
1. Default value validation
2. Enum/constraint validation
3. Unique constraint enforcement
4. Index existence (structural verification)
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.garden.models import (
    KnowledgeCardLink,
    DailyInsight,
    RelationType,
    InsightStatus
)
from agent_os.items.models import Workspace, Item
from agent_os.auth.models import User


# ============================================================================
# Fixtures for Garden Tests
# ============================================================================

@pytest.fixture
async def test_workspace(db_session: AsyncSession) -> Workspace:
    """Create a test workspace"""
    workspace = Workspace(
        name="Test Workspace",
        description="Test Description",
        owner_id=uuid.uuid4()
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user"""
    user = User(
        email=f"test_{uuid.uuid4()}@example.com",
        username=f"testuser_{uuid.uuid4()}",
        password_hash="fake_hash"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_items(db_session: AsyncSession, test_workspace: Workspace) -> tuple[Item, Item]:
    """Create two test items for edge testing"""
    item1 = Item(
        workspace_id=test_workspace.id,
        creator_id=test_workspace.owner_id,
        type="note",
        title="Test Item 1",
        content="Content 1"
    )
    item2 = Item(
        workspace_id=test_workspace.id,
        creator_id=test_workspace.owner_id,
        type="note",
        title="Test Item 2",
        content="Content 2"
    )
    db_session.add_all([item1, item2])
    await db_session.commit()
    await db_session.refresh(item1)
    await db_session.refresh(item2)
    return item1, item2


# ============================================================================
# Test 1: Default Value Tests
# ============================================================================

class TestKnowledgeCardLinkDefaults:
    """Test KnowledgeCardLink default values"""

    @pytest.mark.asyncio
    async def test_default_relation_strength(self, db_session: AsyncSession, test_workspace: Workspace, test_items: tuple):
        """Test that relation_strength defaults to 0.0"""
        item1, item2 = test_items

        link = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item1.id,
            to_id=item2.id,
            type="related"
        )

        db_session.add(link)
        await db_session.commit()
        await db_session.refresh(link)

        assert link.relation_strength == 0.0, "Default relation_strength should be 0.0"

    @pytest.mark.asyncio
    async def test_default_is_active(self, db_session: AsyncSession, test_workspace: Workspace, test_items: tuple):
        """Test that is_active defaults to True"""
        item1, item2 = test_items

        link = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item1.id,
            to_id=item2.id,
            type="related"
        )

        db_session.add(link)
        await db_session.commit()
        await db_session.refresh(link)

        assert link.is_active is True, "Default is_active should be True"


class TestDailyInsightDefaults:
    """Test DailyInsight default values"""

    @pytest.mark.asyncio
    async def test_default_status(self, db_session: AsyncSession, test_workspace: Workspace, test_user: User):
        """Test that status defaults to 'draft'"""
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title="Test Insight",
            content="Test Content"
        )

        db_session.add(insight)
        await db_session.commit()
        await db_session.refresh(insight)

        assert insight.status == "draft", "Default status should be 'draft'"

    @pytest.mark.asyncio
    async def test_default_level(self, db_session: AsyncSession, test_workspace: Workspace, test_user: User):
        """Test that level defaults to 1"""
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title="Test Insight",
            content="Test Content"
        )

        db_session.add(insight)
        await db_session.commit()
        await db_session.refresh(insight)

        assert insight.level == 1, "Default level should be 1"

    @pytest.mark.asyncio
    async def test_default_stability_score(self, db_session: AsyncSession, test_workspace: Workspace, test_user: User):
        """Test that stability_score defaults to 0.0"""
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title="Test Insight",
            content="Test Content"
        )

        db_session.add(insight)
        await db_session.commit()
        await db_session.refresh(insight)

        assert insight.stability_score == 0.0, "Default stability_score should be 0.0"

    @pytest.mark.asyncio
    async def test_default_evidence_count(self, db_session: AsyncSession, test_workspace: Workspace, test_user: User):
        """Test that evidence_count defaults to 1"""
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title="Test Insight",
            content="Test Content"
        )

        db_session.add(insight)
        await db_session.commit()
        await db_session.refresh(insight)

        assert insight.evidence_count == 1, "Default evidence_count should be 1"


# ============================================================================
# Test 2: Enum and Constraint Validation Tests
# ============================================================================

class TestKnowledgeCardLinkConstraints:
    """Test KnowledgeCardLink enum and check constraints"""

    @pytest.mark.asyncio
    async def test_valid_relation_types(self, db_session: AsyncSession, test_workspace: Workspace, test_items: tuple):
        """Test that all valid relation types work"""
        item1, item2 = test_items

        valid_types = ["related", "support", "contradict", "reference"]

        for i, rel_type in enumerate(valid_types):
            # Use different node pairs to avoid unique constraint violation
            from_item = item1 if i % 2 == 0 else item2
            to_item = item2 if i % 2 == 0 else item1

            link = KnowledgeCardLink(
                workspace_id=test_workspace.id,
                from_id=from_item.id,
                to_id=to_item.id,
                type=rel_type
            )
            db_session.add(link)

        await db_session.commit()
        # If we get here without error, the test passes

    @pytest.mark.asyncio
    async def test_invalid_relation_type(self, db_session: AsyncSession, test_workspace: Workspace, test_items: tuple):
        """Test that invalid relation type raises IntegrityError"""
        item1, item2 = test_items

        link = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item1.id,
            to_id=item2.id,
            type="invalid_type"  # Invalid type
        )

        db_session.add(link)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()


class TestDailyInsightConstraints:
    """Test DailyInsight enum and check constraints"""

    @pytest.mark.asyncio
    async def test_valid_status_values(self, db_session: AsyncSession, test_workspace: Workspace, test_user: User):
        """Test that all valid status values work"""
        valid_statuses = ["draft", "candidate", "stable", "rejected"]

        for i, status in enumerate(valid_statuses):
            insight = DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title=f"Test Insight {i}",
                content="Test Content",
                status=status
            )
            db_session.add(insight)

        await db_session.commit()
        # If we get here without error, the test passes

    @pytest.mark.asyncio
    async def test_invalid_status_value(self, db_session: AsyncSession, test_workspace: Workspace, test_user: User):
        """Test that invalid status raises IntegrityError"""
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title="Test Insight",
            content="Test Content",
            status="invalid_status"  # Invalid status
        )

        db_session.add(insight)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_valid_level_values(self, db_session: AsyncSession, test_workspace: Workspace, test_user: User):
        """Test that valid level values (1, 2, 3) work"""
        for level in [1, 2, 3]:
            insight = DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title=f"Test Insight Level {level}",
                content="Test Content",
                level=level
            )
            db_session.add(insight)

        await db_session.commit()

    @pytest.mark.asyncio
    async def test_invalid_level_value(self, db_session: AsyncSession, test_workspace: Workspace, test_user: User):
        """Test that invalid level raises IntegrityError"""
        insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title="Test Insight",
            content="Test Content",
            level=5  # Invalid level (not 1, 2, or 3)
        )

        db_session.add(insight)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_stability_score_range(self, db_session: AsyncSession, test_workspace: Workspace, test_user: User):
        """Test that stability_score must be in [0.0, 1.0]"""
        # Valid values
        for score in [0.0, 0.5, 1.0]:
            insight = DailyInsight(
                workspace_id=test_workspace.id,
                user_id=test_user.id,
                title=f"Test Insight Score {score}",
                content="Test Content",
                stability_score=score
            )
            db_session.add(insight)

        await db_session.commit()

        # Invalid value (should fail)
        bad_insight = DailyInsight(
            workspace_id=test_workspace.id,
            user_id=test_user.id,
            title="Bad Insight",
            content="Bad Content",
            stability_score=1.5  # Out of range
        )
        db_session.add(bad_insight)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()


# ============================================================================
# Test 3: Unique Constraint Tests
# ============================================================================

class TestKnowledgeCardLinkUniqueConstraint:
    """Test KnowledgeCardLink unique constraint (from_id, to_id, type)"""

    @pytest.mark.asyncio
    async def test_unique_constraint_violation(self, db_session: AsyncSession, test_workspace: Workspace, test_items: tuple):
        """Test that duplicate (from_id, to_id, type) raises IntegrityError"""
        item1, item2 = test_items

        # First link
        link1 = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item1.id,
            to_id=item2.id,
            type="related",
            relation_strength=0.8
        )
        db_session.add(link1)
        await db_session.commit()

        # Try to add duplicate
        link2 = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item1.id,
            to_id=item2.id,
            type="related",  # Same type
            relation_strength=0.5
        )
        db_session.add(link2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_different_type_allowed(self, db_session: AsyncSession, test_workspace: Workspace, test_items: tuple):
        """Test that same nodes with different types are allowed"""
        item1, item2 = test_items

        # First link
        link1 = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item1.id,
            to_id=item2.id,
            type="related"
        )
        db_session.add(link1)
        await db_session.commit()

        # Different type should be allowed
        link2 = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item1.id,
            to_id=item2.id,
            type="support"  # Different type
        )
        db_session.add(link2)
        await db_session.commit()  # Should not raise

    @pytest.mark.asyncio
    async def test_reversed_direction_allowed(self, db_session: AsyncSession, test_workspace: Workspace, test_items: tuple):
        """Test that reversed direction (to_id, from_id) is allowed"""
        item1, item2 = test_items

        # First link: item1 -> item2
        link1 = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item1.id,
            to_id=item2.id,
            type="related"
        )
        db_session.add(link1)
        await db_session.commit()

        # Reversed direction: item2 -> item1 (should be allowed)
        link2 = KnowledgeCardLink(
            workspace_id=test_workspace.id,
            from_id=item2.id,
            to_id=item1.id,
            type="related"
        )
        db_session.add(link2)
        await db_session.commit()  # Should not raise


# ============================================================================
# Test 4: Index Verification Tests
# ============================================================================

class TestIndexExistence:
    """Test that required indexes exist in the database schema"""

    @pytest.mark.asyncio
    async def test_knowledge_card_link_indexes(self, engine):
        """Test KnowledgeCardLink indexes exist"""
        from sqlalchemy import inspect as sql_inspect

        # Use async inspection properly
        async with engine.connect() as conn:
            # Run sync inspection on the sync connection
            def get_indexes(conn):
                inspector = sql_inspect(conn)
                return inspector.get_indexes('knowledge_card_links')

            indexes = await conn.run_sync(get_indexes)
            index_names = [idx['name'] for idx in indexes]

            # Check required indexes
            required_indexes = [
                'idx_kcl_workspace',
                'idx_kcl_workspace_strength',
                'idx_kcl_from_id',
                'idx_kcl_to_id'
            ]

            for required in required_indexes:
                assert any(required in name for name in index_names), \
                    f"Index {required} should exist on knowledge_card_links table"

    @pytest.mark.asyncio
    async def test_daily_insight_indexes(self, engine):
        """Test DailyInsight indexes exist"""
        from sqlalchemy import inspect as sql_inspect

        # Use async inspection properly
        async with engine.connect() as conn:
            # Run sync inspection on the sync connection
            def get_indexes(conn):
                inspector = sql_inspect(conn)
                return inspector.get_indexes('daily_insights')

            indexes = await conn.run_sync(get_indexes)
            index_names = [idx['name'] for idx in indexes]

            # Check required indexes (matching ORM definition)
            required_indexes = [
                'idx_di_workspace_user',  #联合索引 workspace_id + user_id
                'idx_di_status',
                'idx_di_created_at',
                'idx_di_canonical_hash'
            ]

            for required in required_indexes:
                assert any(required in name for name in index_names), \
                    f"Index {required} should exist on daily_insights table"


# ============================================================================
# Test 5: ORM Enum Access Tests
# ============================================================================

class TestEnumAccess:
    """Test that enums can be accessed properly"""

    def test_relation_type_enum_values(self):
        """Test RelationType enum has correct values"""
        assert RelationType.RELATED.value == "related"
        assert RelationType.SUPPORT.value == "support"
        assert RelationType.CONTRADICT.value == "contradict"
        assert RelationType.REFERENCE.value == "reference"

    def test_insight_status_enum_values(self):
        """Test InsightStatus enum has correct values"""
        assert InsightStatus.DRAFT.value == "draft"
        assert InsightStatus.CANDIDATE.value == "candidate"
        assert InsightStatus.STABLE.value == "stable"
        assert InsightStatus.REJECTED.value == "rejected"
