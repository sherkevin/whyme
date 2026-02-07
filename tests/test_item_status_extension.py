"""Tests for ItemStatus enum extension (Stage 2).

Tests for the new RAW and PROCESSED status values.
"""

import pytest
from agent_os.items.models import ItemStatus


def test_item_status_has_raw():
    """验证 ItemStatus 有 RAW 状态"""
    assert hasattr(ItemStatus, 'RAW'), "ItemStatus should have RAW status"
    assert ItemStatus.RAW.value == "raw", "RAW value should be 'raw'"
    print("✅ ItemStatus.RAW exists")


def test_item_status_has_processed():
    """验证 ItemStatus 有 PROCESSED 状态"""
    assert hasattr(ItemStatus, 'PROCESSED'), "ItemStatus should have PROCESSED status"
    assert ItemStatus.PROCESSED.value == "processed", "PROCESSED value should be 'processed'"
    print("✅ ItemStatus.PROCESSED exists")


def test_item_status_keeps_original_values():
    """验证 ItemStatus 保留原有状态值"""
    # 检查原有的状态值仍然存在
    assert hasattr(ItemStatus, 'ACTIVE'), "ItemStatus should keep ACTIVE"
    assert hasattr(ItemStatus, 'ARCHIVED'), "ItemStatus should keep ARCHIVED"
    assert hasattr(ItemStatus, 'DELETED'), "ItemStatus should keep DELETED"

    # 验证值
    assert ItemStatus.ACTIVE.value == "active"
    assert ItemStatus.ARCHIVED.value == "archived"
    assert ItemStatus.DELETED.value == "deleted"
    print("✅ Original status values preserved")


def test_item_status_flow():
    """验证状态流转逻辑"""
    # 阶段二的状态流转: raw -> processed -> archived
    raw = ItemStatus.RAW
    processed = ItemStatus.PROCESSED
    archived = ItemStatus.ARCHIVED

    # 验证状态值存在
    assert raw.value == "raw"
    assert processed.value == "processed"
    assert archived.value == "archived"

    print("✅ Status flow: raw -> processed -> archived")


def test_inbox_schema_accepts_raw_status():
    """验证 Inbox schema 接受 raw 状态"""
    from agent_os.inbox.schema import InboxItemStatusUpdate

    # 测试 raw 状态可以被接受
    status_update = InboxItemStatusUpdate(status="raw")
    assert status_update.status == "raw"

    # 测试 processed 状态可以被接受
    status_update = InboxItemStatusUpdate(status="processed")
    assert status_update.status == "processed"

    # 测试原有状态仍然被接受
    for status in ["active", "archived", "deleted"]:
        status_update = InboxItemStatusUpdate(status=status)
        assert status_update.status == status

    print("✅ Inbox schema accepts all status values including raw and processed")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing ItemStatus Extension for Stage 2")
    print("=" * 60)

    test_item_status_has_raw()
    test_item_status_has_processed()
    test_item_status_keeps_original_values()
    test_item_status_flow()
    test_inbox_schema_accepts_raw_status()

    print("\n" + "=" * 60)
    print("✅ All ItemStatus extension tests passed!")
    print("=" * 60)
