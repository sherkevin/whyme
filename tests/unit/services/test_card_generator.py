"""Tests for Card Generator (Stage 2).

Tests the InboxItem → Card conversion logic.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.items.models import Item, ItemStatus, ItemType, Workspace
from agent_os.auth.models import User
from agent_os.knowledge.card_generator import (
    generate_card_from_item,
    _map_item_type_to_para_type,
    _extract_tags,
    check_card_exists
)
from agent_os.knowledge.models import Card


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
async def test_user_with_workspace(db_session: AsyncSession):
    """Create a test user with workspace."""
    import uuid
    from agent_os.auth.security import get_password_hash

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        username="cardtest_user",
        email="cardtest@example.com",
        password_hash=get_password_hash("password123"),
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()

    workspace_id = uuid.uuid4()
    workspace = Workspace(
        id=workspace_id,
        name="Card Test Workspace",
        owner_id=user.id
    )
    db_session.add(workspace)
    await db_session.flush()

    user.default_workspace_id = workspace_id
    await db_session.commit()
    await db_session.refresh(user)

    return {"user": user, "workspace": workspace}


@pytest.fixture
async def processed_item(db_session: AsyncSession, test_user_with_workspace):
    """Create a PROCESSED item for testing."""
    import uuid

    workspace = test_user_with_workspace["workspace"]
    user = test_user_with_workspace["user"]

    item_id = uuid.uuid4()
    item = Item(
        id=item_id,
        workspace_id=workspace.id,
        creator_id=user.id,
        title="Test Task Item",
        content="TODO: Complete the card generator implementation",
        status=ItemStatus.PROCESSED.value,  # Use string value
        type=ItemType.TASK.value,  # Use type field with string value
        summary="Implementation task for card generator",
        source_meta={  # Changed from source_meta
            "classification_confidence": "HIGH",
            "item_subtype": "implementation"
        }
    )
    db_session.add(item)
    await db_session.commit()
    await db_session.refresh(item)

    return item


# ============================================================================
# Test _map_item_type_to_para_type
# ============================================================================

class TestMapItemTypeToParaType:
    """测试 Item 类型到 Card para_type 的映射"""

    def test_map_task_to_action(self, processed_item):
        """验证 TASK 类型映射到 action"""
        processed_item.item_type = ItemType.TASK
        result = _map_item_type_to_para_type(processed_item)
        assert result == "action"

    def test_map_note_to_concept(self, processed_item):
        """验证 NOTE 类型映射到 concept"""
        processed_item.item_type = ItemType.NOTE
        result = _map_item_type_to_para_type(processed_item)
        assert result == "concept"

    def test_map_reference_to_reference(self, processed_item):
        """验证 RESOURCE 类型映射到 reference"""
        processed_item.item_type = ItemType.RESOURCE
        result = _map_item_type_to_para_type(processed_item)
        assert result == "reference"

    def test_map_none_to_reference(self, processed_item):
        """验证 None 类型映射到 reference (默认)"""
        processed_item.item_type = None
        result = _map_item_type_to_para_type(processed_item)
        assert result == "reference"


# ============================================================================
# Test _extract_tags
# ============================================================================

class TestExtractTags:
    """测试标签提取功能"""

    def test_extract_tags_with_item_type(self, processed_item):
        """验证提取 item_type 标签"""
        processed_item.item_type = ItemType.TASK
        tags = _extract_tags(processed_item)
        assert "task" in tags

    def test_extract_tags_with_subtype(self, processed_item):
        """验证提取子类型标签"""
        processed_item.source_meta = {"item_subtype": "implementation"}
        tags = _extract_tags(processed_item)
        assert "implementation" in tags

    def test_extract_tags_with_confidence(self, processed_item):
        """验证提取置信度标签"""
        processed_item.source_meta = {"classification_confidence": "HIGH"}
        tags = _extract_tags(processed_item)
        assert "high-confidence" in tags

    def test_extract_tags_combined(self, processed_item):
        """验证组合标签提取"""
        processed_item.item_type = ItemType.TASK
        processed_item.source_meta = {
            "item_subtype": "implementation",
            "classification_confidence": "HIGH"
        }
        tags = _extract_tags(processed_item)
        assert "task" in tags
        assert "implementation" in tags
        assert "high-confidence" in tags


# ============================================================================
# Test check_card_exists
# ============================================================================

class TestCheckCardExists:
    """测试检查 Card 是否存在"""

    async def test_card_not_exists_for_new_item(self, db_session, processed_item):
        """验证新 Item 没有 Card"""
        exists = await check_card_exists(db_session, str(processed_item.id))
        assert exists is False

    async def test_card_exists_after_creation(self, db_session, processed_item):
        """验证创建 Card 后返回 True"""
        # 先创建 Card
        card = await generate_card_from_item(db_session, str(processed_item.id))

        # 检查是否存在
        exists = await check_card_exists(db_session, str(processed_item.id))
        assert exists is True


# ============================================================================
# Test generate_card_from_item
# ============================================================================

class TestGenerateCardFromItem:
    """测试从 Item 生成 Card"""

    async def test_generate_card_from_processed_item(self, db_session, processed_item):
        """验证从 PROCESSED Item 生成 Card"""
        card = await generate_card_from_item(db_session, str(processed_item.id))

        assert card is not None
        assert card.title == processed_item.title
        assert card.content == processed_item.content
        assert card.para_type == "action"  # TASK -> action
        assert card.source_inbox_item_id == processed_item.id
        assert "task" in card.tags

        print(f"✅ Generated card {card.id} from item {processed_item.id}")

    async def test_generate_card_fails_for_raw_item(self, db_session, test_user_with_workspace):
        """验证从 RAW Item 生成 Card 失败"""
        import uuid

        workspace = test_user_with_workspace["workspace"]
        user = test_user_with_workspace["user"]

        # 创建一个 RAW item
        item = Item(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            creator_id=user.id,
            title="Raw Item",
            content="This is not processed",
            status=ItemStatus.RAW.value,
            type=ItemType.NOTE.value
        )
        db_session.add(item)
        await db_session.commit()

        # 应该抛出 ValueError
        with pytest.raises(ValueError, match="must be in PROCESSED status"):
            await generate_card_from_item(db_session, str(item.id))

    async def test_generate_card_fails_for_nonexistent_item(self, db_session):
        """验证从不存在的 Item 生成 Card 失败"""
        import uuid

        fake_id = uuid.uuid4()
        with pytest.raises(ValueError, match="Item not found"):
            await generate_card_from_item(db_session, str(fake_id))

    async def test_generate_card_for_note_item(self, db_session, test_user_with_workspace):
        """验证从 NOTE Item 生成 concept Card"""
        import uuid

        workspace = test_user_with_workspace["workspace"]
        user = test_user_with_workspace["user"]

        item = Item(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            creator_id=user.id,
            title="Concept Note",
            content="Key concept about the system architecture",
            status=ItemStatus.PROCESSED.value,
            type=ItemType.NOTE.value,
            summary="Architecture notes"
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        card = await generate_card_from_item(db_session, str(item.id))

        assert card.para_type == "concept"  # NOTE -> concept
        assert "note" in card.tags

        print(f"✅ Generated concept card from note item")

    async def test_generate_card_for_reference_item(self, db_session, test_user_with_workspace):
        """验证从 RESOURCE Item 生成 reference Card"""
        import uuid

        workspace = test_user_with_workspace["workspace"]
        user = test_user_with_workspace["user"]

        item = Item(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            creator_id=user.id,
            title="Reference Link",
            content="https://example.com/documentation",
            status=ItemStatus.PROCESSED.value,
            type=ItemType.RESOURCE.value,
            summary="External documentation"
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        card = await generate_card_from_item(db_session, str(item.id))

        assert card.para_type == "reference"  # RESOURCE -> reference
        assert "resource" in card.tags

        print(f"✅ Generated reference card from resource item")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Card Generator for Stage 2")
    print("=" * 60)
    print()

    pytest.main([__file__, "-v", "--tb=short"])
