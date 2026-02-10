"""Tests for Agent core processor (Stage 2).

Tests for the processor.py module that processes InboxItems.
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.agent.processor import (
    process_inbox_item,
    process_multiple_items,
    get_raw_items,
    agent_tick,
    ProcessingResult
)
from agent_os.items.models import Item, ItemStatus, Workspace
from agent_os.agent.classifier import ItemType
from agent_os.auth.models import User
from agent_os.auth.security import get_password_hash


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user with workspace."""
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        username="processor_test_user",
        email="processor_test@example.com",
        password_hash=get_password_hash("password123"),
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()

    workspace_id = uuid.uuid4()
    workspace = Workspace(
        id=workspace_id,
        name="Processor Test Workspace",
        owner_id=user.id
    )
    db_session.add(workspace)
    await db_session.flush()

    user.default_workspace_id = workspace_id
    await db_session.commit()
    await db_session.refresh(user)

    return user


@pytest.mark.asyncio
class TestProcessInboxItem:
    """测试 process_inbox_item 函数"""

    async def test_process_raw_item_success(self, db_session: AsyncSession, test_user):
        """验证成功处理 raw 状态的 item"""
        # 创建一个 raw 状态的 item
        item = Item(
            id=uuid.uuid4(),
            workspace_id=test_user.default_workspace_id,
            creator_id=test_user.id,
            title="",  # 空标题，需要生成
            content="TODO: Implement user authentication system",
            status=ItemStatus.RAW.value,
            type="note"  # Use type field instead of item_type
        )
        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        item_id = str(item.id)

        # 处理 item
        result = await process_inbox_item(db_session, item_id)

        # 验证结果
        assert result.success is True
        assert result.item_id == item_id
        assert result.from_status == ItemStatus.RAW
        assert result.to_status == ItemStatus.PROCESSED
        assert result.title is not None
        assert len(result.title) > 0
        assert result.item_type == ItemType.TASK
        assert result.error is None

        # 验证数据库已更新
        from sqlalchemy import select
        stmt = select(Item).where(Item.id == item.id)
        updated_item_result = await db_session.execute(stmt)
        updated_item = updated_item_result.scalar_one()
        assert updated_item.status == ItemStatus.PROCESSED.value
        assert updated_item.title == result.title
        assert updated_item.summary is not None

        print(f"✅ Processed item: {result.title}")

    async def test_process_item_with_existing_title(self, db_session: AsyncSession, test_user):
        """验证处理已有标题的 item"""
        from agent_os.items.crud import item_crud

        item_data = {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "title": "Existing Title",
            "content": "Some content here",
            "status": ItemStatus.RAW
        }

        item = await item_crud.create(db_session, item_data)

        result = await process_inbox_item(db_session, str(item.id))

        assert result.success is True
        assert result.title == "Existing Title"  # 应该保留已有标题

        print("✅ Existing title preserved")

    async def test_process_note_item(self, db_session: AsyncSession, test_user):
        """验证处理笔记类型 item"""
        from agent_os.items.crud import item_crud

        item_data = {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "content": "Meeting notes: Discussed project roadmap and milestones",
            "status": ItemStatus.RAW
        }

        item = await item_crud.create(db_session, item_data)

        result = await process_inbox_item(db_session, str(item.id))

        assert result.success is True
        assert result.item_type == ItemType.NOTE

        print(f"✅ Note item classified: {result.item_type}")

    async def test_process_reference_item(self, db_session: AsyncSession, test_user):
        """验证处理参考类型 item"""
        from agent_os.items.crud import item_crud

        item_data = {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "content": "Check out this article: https://example.com/guide",
            "status": ItemStatus.RAW
        }

        item = await item_crud.create(db_session, item_data)

        result = await process_inbox_item(db_session, str(item.id))

        assert result.success is True
        assert result.item_type == ItemType.REFERENCE

        print(f"✅ Reference item classified: {result.item_type}")

    async def test_process_nonexistent_item(self, db_session: AsyncSession):
        """验证处理不存在的 item"""
        result = await process_inbox_item(db_session, "nonexistent-id")

        assert result.success is False
        assert "not found" in result.error.lower()

        print("✅ Nonexistent item handled correctly")

    async def test_process_already_processed_item_skipped(self, db_session: AsyncSession, test_user):
        """验证已处理的 item 会被跳过"""
        from agent_os.items.crud import item_crud

        item_data = {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "title": "Already Processed",
            "content": "Some content",
            "status": ItemStatus.PROCESSED  # 已经是 processed 状态
        }

        item = await item_crud.create(db_session, item_data)

        result = await process_inbox_item(db_session, str(item.id), force_reprocess=False)

        assert result.success is True
        assert result.metadata.get("skipped") == "already processed"
        assert result.to_status == ItemStatus.PROCESSED

        print("✅ Already processed item skipped")

    async def test_process_item_generates_summary(self, db_session: AsyncSession, test_user):
        """验证生成摘要"""
        from agent_os.items.crud import item_crud

        long_content = "This is a long content. " * 20

        item_data = {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "content": long_content,
            "status": ItemStatus.RAW
        }

        item = await item_crud.create(db_session, item_data)

        result = await process_inbox_item(db_session, str(item.id))

        assert result.success is True
        assert result.summary is not None
        assert len(result.summary) > 0
        assert len(result.summary) <= 500  # 摘要应该被截断

        print(f"✅ Summary generated: {len(result.summary)} chars")


@pytest.mark.asyncio
class TestProcessMultipleItems:
    """测试 process_multiple_items 函数"""

    async def test_process_multiple_success(self, db_session: AsyncSession, test_user):
        """验证批量处理成功"""
        from agent_os.items.crud import item_crud

        # 创建多个 raw items
        item_ids = []
        for i in range(3):
            item_data = {
                "user_id": test_user.id,
                "workspace_id": test_user.default_workspace_id,
                "content": f"Task {i}: Complete this item",
                "status": ItemStatus.RAW
            }
            item = await item_crud.create(db_session, item_data)
            item_ids.append(str(item.id))

        # 批量处理
        results = await process_multiple_items(db_session, item_ids)

        assert len(results) == 3
        assert all(r.success for r in results)

        print(f"✅ Processed {len(results)} items successfully")

    async def test_process_multiple_with_mixed_results(self, db_session: AsyncSession, test_user):
        """验证混合结果的处理"""
        from agent_os.items.crud import item_crud

        # 创建一个有效 item
        item_data = {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "content": "Valid task",
            "status": ItemStatus.RAW
        }
        item = await item_crud.create(db_session, item_data)

        # 混合有效和无效 ID
        item_ids = [str(item.id), "invalid-id-1", "invalid-id-2"]

        results = await process_multiple_items(db_session, item_ids, stop_on_error=False)

        assert len(results) == 3
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is False

        print("✅ Mixed results handled correctly")

    async def test_process_multiple_stop_on_error(self, db_session: AsyncSession, test_user):
        """验证遇到错误时停止"""
        from agent_os.items.crud import item_crud

        # 创建两个 items
        item1 = await item_crud.create(db_session, {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "content": "First task",
            "status": ItemStatus.RAW
        })

        item2 = await item_crud.create(db_session, {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "content": "Second task",
            "status": ItemStatus.RAW
        })

        # 包含无效 ID
        item_ids = [str(item1.id), "invalid-id", str(item2.id)]

        results = await process_multiple_items(db_session, item_ids, stop_on_error=True)

        # 应该在遇到错误后停止
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False

        print("✅ Stopped on error as expected")


@pytest.mark.asyncio
class TestGetRawItems:
    """测试 get_raw_items 函数"""

    async def test_get_raw_items_empty(self, db_session: AsyncSession):
        """验证没有 raw items 时返回空列表"""
        items = await get_raw_items(db_session)

        assert items == []

        print("✅ Empty raw items list returned")

    async def test_get_raw_items_with_data(self, db_session: AsyncSession, test_user):
        """验证获取 raw items"""
        from agent_os.items.crud import item_crud

        # 创建 raw items
        for i in range(3):
            await item_crud.create(db_session, {
                "user_id": test_user.id,
                "workspace_id": test_user.default_workspace_id,
                "content": f"Raw item {i}",
                "status": ItemStatus.RAW
            })

        # 创建 processed items（不应该被返回）
        await item_crud.create(db_session, {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "content": "Processed item",
            "status": ItemStatus.PROCESSED
        })

        raw_items = await get_raw_items(db_session, limit=10)

        assert len(raw_items) == 3
        assert all(item.status == ItemStatus.RAW for item in raw_items)

        print(f"✅ Retrieved {len(raw_items)} raw items")

    async def test_get_raw_items_limit(self, db_session: AsyncSession, test_user):
        """验证限制返回数量"""
        from agent_os.items.crud import item_crud

        # 创建5个 raw items
        for i in range(5):
            await item_crud.create(db_session, {
                "user_id": test_user.id,
                "workspace_id": test_user.default_workspace_id,
                "content": f"Raw item {i}",
                "status": ItemStatus.RAW
            })

        raw_items = await get_raw_items(db_session, limit=3)

        assert len(raw_items) == 3

        print("✅ Limit applied correctly")


@pytest.mark.asyncio
class TestAgentTick:
    """测试 agent_tick 函数"""

    async def test_agent_tick_no_items(self, db_session: AsyncSession):
        """验证没有 raw items 时的 tick"""
        result = await agent_tick(db_session, max_items=10)

        assert result["processed"] == 0
        assert result["succeeded"] == 0
        assert result["failed"] == 0
        assert result["skipped"] == 0
        assert result["results"] == []

        print("✅ Agent tick with no items handled correctly")

    async def test_agent_tick_with_items(self, db_session: AsyncSession, test_user):
        """验证处理 raw items 的 tick"""
        from agent_os.items.crud import item_crud

        # 创建 raw items
        for i in range(3):
            await item_crud.create(db_session, {
                "user_id": test_user.id,
                "workspace_id": test_user.default_workspace_id,
                "content": f"Task {i}: Complete this",
                "status": ItemStatus.RAW
            })

        result = await agent_tick(db_session, max_items=10)

        assert result["processed"] == 3
        assert result["succeeded"] == 3
        assert result["failed"] == 0
        assert len(result["results"]) == 3

        print(f"✅ Agent tick processed {result['succeeded']} items")

    async def test_agent_tick_respects_max_items(self, db_session: AsyncSession, test_user):
        """验证 max_items 限制"""
        from agent_os.items.crud import item_crud

        # 创建 10 个 raw items
        for i in range(10):
            await item_crud.create(db_session, {
                "user_id": test_user.id,
                "workspace_id": test_user.default_workspace_id,
                "content": f"Task {i}",
                "status": ItemStatus.RAW
            })

        result = await agent_tick(db_session, max_items=5)

        assert result["processed"] == 5
        assert result["succeeded"] == 5

        print("✅ Max items limit respected")

    async def test_agent_tick_with_mixed_items(self, db_session: AsyncSession, test_user):
        """验证混合状态 items 的 tick"""
        from agent_os.items.crud import item_crud

        # 创建 raw items
        for i in range(2):
            await item_crud.create(db_session, {
                "user_id": test_user.id,
                "workspace_id": test_user.default_workspace_id,
                "content": f"Raw task {i}",
                "status": ItemStatus.RAW
            })

        # 创建 processed items
        await item_crud.create(db_session, {
            "user_id": test_user.id,
            "workspace_id": test_user.default_workspace_id,
            "content": "Already processed",
            "status": ItemStatus.PROCESSED
        })

        result = await agent_tick(db_session, max_items=10)

        # 应该只处理 raw items
        assert result["processed"] == 2
        assert result["succeeded"] == 2

        print("✅ Only raw items processed")


@pytest.mark.asyncio
class TestProcessingResult:
    """测试 ProcessingResult 类"""

    def test_processing_result_to_dict(self):
        """验证转换为字典"""
        result = ProcessingResult(
            success=True,
            item_id="test-id",
            from_status=ItemStatus.RAW,
            to_status=ItemStatus.PROCESSED,
            title="Test Title",
            summary="Test summary",
            item_type=ItemType.TASK
        )

        result_dict = result.to_dict()

        assert result_dict["success"] is True
        assert result_dict["item_id"] == "test-id"
        assert result_dict["from_status"] == "raw"
        assert result_dict["to_status"] == "processed"
        assert result_dict["title"] == "Test Title"
        assert result_dict["item_type"] == "task"
        assert "processed_at" in result_dict

        print("✅ ProcessingResult to_dict works correctly")

    def test_processing_result_error(self):
        """验证错误结果"""
        result = ProcessingResult(
            success=False,
            item_id="test-id",
            error="Item not found"
        )

        assert result.success is False
        assert result.error == "Item not found"
        assert result.item_id == "test-id"

        result_dict = result.to_dict()
        assert result_dict["error"] == "Item not found"

        print("✅ Error result created correctly")


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Agent Processor for Stage 2")
    print("=" * 60)
    print()

    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
