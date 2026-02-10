"""Tests for Agent models (Stage 2).

Tests for the AgentProcessEvent model.
"""

import pytest
from datetime import datetime
from sqlalchemy import select

from agent_os.agent.models import AgentProcessEvent
from agent_os.items.models import Item, ItemStatus


@pytest.mark.asyncio
class TestAgentProcessEvent:
    """测试 AgentProcessEvent 模型"""

    async def test_create_process_event(self, db_session):
        """验证创建处理事件"""
        event = AgentProcessEvent(
            item_id="test-item-id",
            from_status="raw",
            to_status="processed",
            result_summary={
                "title": "Generated Title",
                "summary_length": 150,
                "item_type": "task",
                "confidence": "high"
            }
        )

        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        assert event.id is not None
        assert event.event_id is not None
        assert event.item_id == "test-item-id"
        assert event.from_status == "raw"
        assert event.to_status == "processed"
        assert event.result_summary["item_type"] == "task"
        assert event.processed_at is not None
        assert event.created_at is not None

        print(f"✅ Created event: {event}")

    async def test_process_event_with_error(self, db_session):
        """验证记录错误的事件"""
        event = AgentProcessEvent(
            item_id="test-item-id",
            from_status="raw",
            to_status="raw",  # 状态未改变
            error_message="Processing failed: content too long"
        )

        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        assert event.error_message is not None
        assert "Processing failed" in event.error_message
        assert event.to_status == "raw"  # 状态应该保持不变

        print("✅ Error event created")

    async def test_process_event_with_metadata(self, db_session):
        """验证带元数据的事件"""
        event = AgentProcessEvent(
            item_id="test-item-id",
            from_status="raw",
            to_status="processed",
            result_summary={"success": True},
            metadata={
                "processing_time_ms": 123,
                "processor_version": "1.0",
                "forced_reprocess": False
            }
        )

        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        assert event.metadata["processing_time_ms"] == 123
        assert event.metadata["processor_version"] == "1.0"
        assert event.metadata["forced_reprocess"] is False

        print("✅ Event with metadata created")

    async def test_process_event_relationship_to_item(self, db_session, sample_workspace_id):
        """验证事件与 Item 的关系（简化版）"""
        # 先创建一个 Workspace
        workspace = Workspace(
            id=sample_workspace_id,
            name="Test Workspace"
        )
        db_session.add(workspace)
        await db_session.commit()

        # 创建一个 Item
        item = Item(
            title="Test Item",
            content="Test content",
            status=ItemStatus.RAW,
            workspace_id=sample_workspace_id
        )

        db_session.add(item)
        await db_session.commit()
        await db_session.refresh(item)

        # 创建事件
        event = AgentProcessEvent(
            item_id=str(item.id),
            from_status="raw",
            to_status="processed",
            result_summary={"title": "Test Item"}
        )

        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # 验证关系
        assert event.item_id == str(item.id)
        assert event.from_status == "raw"
        assert event.to_status == "processed"

        print("✅ Event-Item relationship works")

    async def test_multiple_events_for_same_item(self, db_session):
        """验证同一 Item 的多个事件"""
        item_id = "test-item-id"

        # 创建多个事件
        events = [
            AgentProcessEvent(
                item_id=item_id,
                from_status="raw",
                to_status="processed"
            ),
            AgentProcessEvent(
                item_id=item_id,
                from_status="processed",
                to_status="processed",
                metadata={"forced_reprocess": True}
            )
        ]

        for event in events:
            db_session.add(event)

        await db_session.commit()

        # 查询该 Item 的所有事件
        stmt = select(AgentProcessEvent).where(AgentProcessEvent.item_id == item_id)
        result = await db_session.execute(stmt)
        fetched_events = result.scalars().all()

        assert len(fetched_events) == 2
        assert all(e.item_id == item_id for e in fetched_events)

        print("✅ Multiple events for same item tracked")

    async def test_process_event_defaults(self, db_session):
        """验证默认值"""
        event = AgentProcessEvent(
            item_id="test-item-id",
            from_status="raw",
            to_status="processed"
        )

        db_session.add(event)
        await db_session.commit()
        await db_session.refresh(event)

        # 验证默认值
        assert event.result_summary is not None
        assert isinstance(event.result_summary, dict)
        assert event.event_metadata is not None
        assert isinstance(event.event_metadata, dict)
        assert event.processed_at is not None
        assert isinstance(event.processed_at, datetime)
        assert event.created_at is not None
        assert isinstance(event.created_at, datetime)

        print("✅ Default values correct")

    async def test_process_event_unique_event_id(self, db_session):
        """验证 event_id 唯一性"""
        event1 = AgentProcessEvent(
            item_id="item-1",
            from_status="raw",
            to_status="processed"
        )

        event2 = AgentProcessEvent(
            item_id="item-2",
            from_status="raw",
            to_status="processed"
        )

        db_session.add(event1)
        db_session.add(event2)
        await db_session.commit()
        await db_session.refresh(event1)
        await db_session.refresh(event2)

        # event_id 应该不同
        assert event1.event_id != event2.event_id
        assert len(event1.event_id) == 36  # UUID 格式

        print("✅ Unique event_id generated")


# ============================================================================
# Test Execution
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Agent Models for Stage 2")
    print("=" * 60)
    print()

    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
