"""Unit tests for Card Generator (Stage 2).

Tests the InboxItem → Card conversion logic without database dependencies.
"""

from unittest.mock import Mock

import pytest

from agent_os.items.models import ItemStatus, ItemType
from agent_os.knowledge.card_generator import _extract_tags, _map_item_type_to_para_type

# ============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_item():
    """创建一个 mock Item 对象"""
    item = Mock()
    item.id = "test-item-id"
    item.title = "Test Item"
    item.content = "Test content"
    item.item_type = ItemType.TASK
    item.status = ItemStatus.PROCESSED
    item.source_meta = {
        "classification_confidence": "HIGH",
        "item_subtype": "implementation"
    }
    return item


# ============================================================================
# Test _map_item_type_to_para_type
# ============================================================================

class TestMapItemTypeToParaType:
    """测试 Item 类型到 Card para_type 的映射"""

    def test_map_task_to_action(self, mock_item):
        """验证 TASK 类型映射到 action"""
        mock_item.item_type = ItemType.TASK
        result = _map_item_type_to_para_type(mock_item)
        assert result == "action"
        print("✅ TASK -> action")

    def test_map_note_to_concept(self, mock_item):
        """验证 NOTE 类型映射到 concept"""
        mock_item.item_type = ItemType.NOTE
        result = _map_item_type_to_para_type(mock_item)
        assert result == "concept"
        print("✅ NOTE -> concept")

    def test_map_resource_to_reference(self, mock_item):
        """验证 RESOURCE 类型映射到 reference"""
        mock_item.item_type = ItemType.RESOURCE
        result = _map_item_type_to_para_type(mock_item)
        assert result == "reference"
        print("✅ RESOURCE -> reference")

    def test_map_insight_to_concept(self, mock_item):
        """验证 INSIGHT 类型映射到 concept"""
        mock_item.item_type = ItemType.INSIGHT
        result = _map_item_type_to_para_type(mock_item)
        assert result == "concept"
        print("✅ INSIGHT -> concept")

    def test_map_plan_to_reference(self, mock_item):
        """验证 PLAN 类型映射到 reference"""
        mock_item.item_type = ItemType.PLAN
        result = _map_item_type_to_para_type(mock_item)
        assert result == "reference"
        print("✅ PLAN -> reference")

    def test_map_none_to_reference(self, mock_item):
        """验证 None 类型映射到 reference (默认)"""
        mock_item.item_type = None
        result = _map_item_type_to_para_type(mock_item)
        assert result == "reference"
        print("✅ None -> reference (default)")

    def test_map_string_item_type(self, mock_item):
        """验证字符串 item_type 也能正确映射"""
        mock_item.item_type = "task"  # 字符串形式
        result = _map_item_type_to_para_type(mock_item)
        assert result == "action"
        print("✅ String 'task' -> action")


# ============================================================================
# Test _extract_tags
# ============================================================================

class TestExtractTags:
    """测试标签提取功能"""

    def test_extract_tags_with_item_type(self, mock_item):
        """验证提取 item_type 标签"""
        mock_item.item_type = ItemType.TASK
        tags = _extract_tags(mock_item)
        assert "task" in tags
        print("✅ Extract item_type tag")

    def test_extract_tags_with_subtype(self, mock_item):
        """验证提取子类型标签"""
        mock_item.source_meta = {"item_subtype": "implementation"}
        tags = _extract_tags(mock_item)
        assert "implementation" in tags
        print("✅ Extract subtype tag")

    def test_extract_tags_with_high_confidence(self, mock_item):
        """验证提取高置信度标签"""
        mock_item.source_meta = {"classification_confidence": "high"}
        tags = _extract_tags(mock_item)
        assert "high-confidence" in tags
        print("✅ Extract high-confidence tag")

    def test_extract_tags_with_medium_confidence(self, mock_item):
        """验证提取中等置信度标签"""
        mock_item.source_meta = {"classification_confidence": "medium"}
        tags = _extract_tags(mock_item)
        assert "medium-confidence" in tags
        print("✅ Extract medium-confidence tag")

    def test_extract_tags_with_low_confidence(self, mock_item):
        """验证提取低置信度标签"""
        mock_item.source_meta = {"classification_confidence": "low"}
        tags = _extract_tags(mock_item)
        assert "low-confidence" in tags
        print("✅ Extract low-confidence tag")

    def test_extract_tags_combined(self, mock_item):
        """验证组合标签提取"""
        mock_item.item_type = ItemType.TASK
        mock_item.source_meta = {
            "item_subtype": "implementation",
            "classification_confidence": "high"
        }
        tags = _extract_tags(mock_item)
        assert "task" in tags
        assert "implementation" in tags
        assert "high-confidence" in tags
        print(f"✅ Extract combined tags: {tags}")

    def test_extract_tags_empty_metadata(self, mock_item):
        """验证空元数据时的标签提取"""
        mock_item.item_type = ItemType.NOTE
        mock_item.source_meta = None
        tags = _extract_tags(mock_item)
        assert "note" in tags
        assert len(tags) == 1
        print("✅ Extract tags with None metadata")

    def test_extract_tags_no_subtype(self, mock_item):
        """验证没有子类型时的标签提取"""
        mock_item.item_type = ItemType.RESOURCE
        mock_item.source_meta = {"classification_confidence": "medium"}
        tags = _extract_tags(mock_item)
        assert "resource" in tags
        assert "medium-confidence" in tags
        assert "implementation" not in tags  # 不应该有这个标签
        print("✅ Extract tags without subtype")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Card Generator (Unit Tests) for Stage 2")
    print("=" * 60)
    print()

    pytest.main([__file__, "-v", "--tb=short"])
