"""Card Generator for PA 1.0 Stage 2.

Generates Card objects from processed Items.
"""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.items.models import Item, ItemStatus, ItemType
from agent_os.knowledge.models import Card


async def generate_card_from_item(
    db: AsyncSession,
    item_id: str
) -> Card | None:
    """从处理后的 InboxItem 生成 Card.

    Args:
        db: 数据库会话
        item_id: Item ID (字符串或UUID)

    Returns:
        生成的 Card 对象，如果失败则返回 None

    Raises:
        ValueError: 如果 Item 状态不是 PROCESSED 或 Item 不存在
    """
    # 1. 从数据库加载 Item
    from sqlalchemy import select

    # 转换为 UUID
    try:
        item_uuid = uuid.UUID(item_id) if isinstance(item_id, str) else item_id
    except ValueError:
        raise ValueError(f"Invalid item ID format: {item_id}")

    # 查询 Item
    stmt = select(Item).where(Item.id == item_uuid)
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()

    if not item:
        raise ValueError(f"Item not found: {item_id}")

    # 2. 检查状态必须是 PROCESSED
    # Handle both string status and enum status for backward compatibility
    current_status = item.status.value if hasattr(item.status, 'value') else item.status
    if current_status != ItemStatus.PROCESSED.value:
        raise ValueError(
            f"Item must be in PROCESSED status to generate Card. "
            f"Current status: {current_status}"
        )

    # 2. 映射 item_type 到 card.para_type
    para_type = _map_item_type_to_para_type(item)

    # 3. 获取 workspace_id 和 user_id
    user_id = item.creator_id
    workspace_id = item.workspace_id

    # 4. 创建 Card
    card = Card(
        workspace_id=workspace_id,
        user_id=user_id,
        title=item.title or "Untitled",
        content=item.content or "",
        para_type=para_type,
        tags=_extract_tags(item),
        source_inbox_item_id=item.id
    )

    # 5. 保存到数据库
    try:
        db.add(card)
        await db.commit()
        await db.refresh(card)
        return card
    except Exception as e:
        await db.rollback()
        raise RuntimeError(f"Failed to create Card: {e}")


def _map_item_type_to_para_type(item: Item) -> str:
    """映射 Item 类型到 Card para_type.

    Args:
        item: Item 对象

    Returns:
        para_type 字符串
    """
    if not item.item_type:
        return "reference"  # 默认类型

    item_type = item.item_type if isinstance(item.item_type, ItemType) else ItemType(item.item_type)

    # 映射规则:
    # - task -> action (可执行的任务)
    # - note -> concept (知识点)
    # - resource/plan/insight -> reference (参考资料)
    type_mapping = {
        ItemType.TASK: "action",
        ItemType.NOTE: "concept",
        ItemType.RESOURCE: "reference",
        ItemType.PLAN: "reference",
        ItemType.INSIGHT: "concept"  # insight 也是一种概念
    }

    return type_mapping.get(item_type, "reference")


def _extract_tags(item: Item) -> list:
    """从 Item 中提取标签.

    Args:
        item: Item 对象

    Returns:
        标签列表
    """
    tags = []

    # 添加 item_type 作为标签
    if item.item_type:
        tags.append(item.item_type.value)

    # 添加子类型标签 (如果有)
    metadata = item.source_meta or {}  # 使用 source_meta 而不是 source_metadata
    if isinstance(metadata, dict) and "item_subtype" in metadata:
        tags.append(metadata["item_subtype"])

    # 根据分类置信度添加标签
    if isinstance(metadata, dict) and "classification_confidence" in metadata:
        confidence = metadata["classification_confidence"].lower() if isinstance(metadata["classification_confidence"], str) else metadata["classification_confidence"]
        if confidence == "high":
            tags.append("high-confidence")
        elif confidence == "medium":
            tags.append("medium-confidence")
        elif confidence == "low":
            tags.append("low-confidence")

    return tags


async def check_card_exists(
    db: AsyncSession,
    item_id: str
) -> bool:
    """检查 Item 是否已经生成过 Card.

    Args:
        db: 数据库会话
        item_id: Item ID

    Returns:
        如果 Card 已存在返回 True，否则返回 False
    """
    try:
        # 将 item_id 转换为 UUID
        item_uuid = uuid.UUID(item_id) if isinstance(item_id, str) else item_id

        stmt = select(Card).where(Card.source_inbox_item_id == item_uuid)
        result = await db.execute(stmt)
        card = result.scalar_one_or_none()
        return card is not None
    except (ValueError, TypeError):
        # 如果 ID 转换失败，假设 Card 不存在
        return False
