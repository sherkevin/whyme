"""Agent core processor for Stage 2.

This module processes InboxItems, transforming them from raw to processed status.
Part of PA 1.0 Stage 2 implementation.
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.items.models import Item, ItemStatus
from agent_os.agent.title_generator import generate_title, generate_title_from_metadata
from agent_os.agent.summarizer import generate_summary, calculate_summary_quality
from agent_os.agent.classifier import classify_content, ItemType, infer_subtype

# Import LLM processor for optional LLM-based processing
USE_LLM_PROCESSING = os.getenv("USE_LLM_PROCESSING", "false").lower() == "true"
if USE_LLM_PROCESSING:
    from agent_os.agent.llm_processor import (
        generate_summary_llm,
        generate_tags_llm,
        generate_summary_and_tags_llm,
    )


logger = logging.getLogger(__name__)


class ProcessingResult:
    """处理结果."""

    def __init__(
        self,
        success: bool,
        item_id: Optional[str] = None,
        from_status: Optional[ItemStatus] = None,
        to_status: Optional[ItemStatus] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        item_type: Optional[ItemType] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.item_id = item_id
        self.from_status = from_status
        self.to_status = to_status
        self.title = title
        self.summary = summary
        self.item_type = item_type
        self.error = error
        self.metadata = metadata or {}
        self.processed_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典."""
        # 处理 from_status 和 to_status - 可能是枚举或字符串
        from_status_val = self.from_status.value if hasattr(self.from_status, 'value') else str(self.from_status) if self.from_status else None
        to_status_val = self.to_status.value if hasattr(self.to_status, 'value') else str(self.to_status) if self.to_status else None

        return {
            "success": self.success,
            "item_id": str(self.item_id) if self.item_id else None,
            "from_status": from_status_val,
            "to_status": to_status_val,
            "title": self.title,
            "summary": self.summary,
            "item_type": self.item_type.value if self.item_type else None,
            "error": self.error,
            "metadata": self.metadata,
            "processed_at": self.processed_at.isoformat()
        }


async def process_inbox_item(
    db: AsyncSession,
    item_id: str,
    force_reprocess: bool = False
) -> ProcessingResult:
    """处理单个 InboxItem.

    从 raw 状态转换为 processed 状态，生成标题、摘要和类型.

    Args:
        db: 数据库会话
        item_id: Item ID
        force_reprocess: 是否强制重新处理（即使已经是 processed 状态）

    Returns:
        ProcessingResult 对象
    """
    try:
        # 1. 获取 Item - 直接查询而不是使用 CRUD
        import uuid
        from sqlalchemy import select

        # 将字符串转换为 UUID
        try:
            item_uuid = uuid.UUID(item_id) if isinstance(item_id, str) else item_id
        except ValueError:
            return ProcessingResult(
                success=False,
                item_id=str(item_id),
                error=f"Invalid item ID format: {item_id}"
            )

        stmt = select(Item).where(Item.id == item_uuid)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            return ProcessingResult(
                success=False,
                item_id=str(item_id),
                error=f"Item not found: {item_id}"
            )

        # 2. 检查状态（幂等性控制）
        from_status = item.status

        if not force_reprocess and item.status != ItemStatus.RAW:
            # 已经处理过，跳过
            return ProcessingResult(
                success=True,
                item_id=str(item.id),
                from_status=from_status,
                to_status=item.status,
                title=item.title,
                summary=item.summary,
                item_type=ItemType(item.item_type) if item.item_type else None,
                error=None,
                metadata={"skipped": "already processed", "current_status": item.status.value}
            )

        # 3. 生成标题
        content = item.content or ""
        metadata = item.source_meta or {}  # 使用 source_meta 而不是 source_metadata

        if item.title:
            # 已有标题，使用已有标题
            title = item.title
        else:
            # 从内容或元数据生成标题
            title = generate_title_from_metadata(content, metadata, max_length=200)

        # 4. 生成摘要和标签 (LLM 或规则)
        if USE_LLM_PROCESSING:
            # 使用 LLM 生成 summary 和 tags
            try:
                llm_result = await generate_summary_and_tags_llm(content, max_length=500, max_tags=8)
                summary = llm_result.get("summary", "")
                tags = llm_result.get("tags", [])
                metadata["llm_summary"] = True
                metadata["llm_tags"] = tags
                logger.info(f"LLM generated summary and tags for item {item_id}")
            except Exception as e:
                logger.warning(f"LLM processing failed for item {item_id}, falling back to rules: {e}")
                # Fallback to rule-based processing
                summary = generate_summary(content, max_length=500)
                tags = []
                metadata["llm_fallback"] = True
        else:
            # 使用规则生成 summary
            summary = generate_summary(content, max_length=500)
            tags = []

        # 计算摘要质量
        quality_metrics = calculate_summary_quality(summary, len(content))
        metadata["summary_quality"] = quality_metrics

        # 保存 tags 到 metadata
        if tags:
            metadata["tags"] = tags

        # 5. 分类内容
        item_type, confidence = classify_content(content, title, metadata)
        metadata["classification_confidence"] = confidence.value

        # 推断子类型
        subtype = infer_subtype(content, item_type)
        if subtype:
            metadata["item_subtype"] = subtype

        # 6. 更新 Item - 直接修改对象属性
        item.title = title
        item.summary = summary
        item.type = item_type.value  # Update the type column
        item.item_type = item_type  # Also store enum for Card generator
        item.status = ItemStatus.PROCESSED
        item.source_meta = metadata  # 使用 source_meta

        # 提交更改
        await db.commit()
        await db.refresh(item)

        # 7. 记录处理事件（创建 AgentProcessEvent）
        await _record_processing_event(
            db,
            item_id=str(item.id),
            from_status=from_status,
            to_status=ItemStatus.PROCESSED,
            result={
                "title": title,
                "summary_length": len(summary),
                "item_type": item_type.value,
                "confidence": confidence.value
            }
        )

        # 8. 生成 Card (InboxItem → Card 转换)
        try:
            from agent_os.knowledge.card_generator import generate_card_from_item
            card = await generate_card_from_item(db, item)  # 传递 Item 对象而不是 ID
            metadata["card_id"] = str(card.id)
            metadata["card_generation"] = "success"
            logger.info(f"Generated card {card.id} from item {item_id}")
        except Exception as e:
            # Card 生成失败不应导致整个处理失败
            logger.warning(f"Failed to generate card for item {item_id}: {str(e)}")
            metadata["card_generation_error"] = str(e)

        # 更新 metadata 到数据库
        item.source_meta = metadata
        await db.commit()
        await db.refresh(item)

        logger.info(f"Processed item {item_id}: {item_type.value} with {confidence.value} confidence")

        return ProcessingResult(
            success=True,
            item_id=str(item.id),
            from_status=from_status,
            to_status=ItemStatus.PROCESSED,
            title=title,
            summary=summary,
            item_type=item_type,
            metadata=metadata
        )

    except Exception as e:
        logger.error(f"Error processing item {item_id}: {str(e)}", exc_info=True)

        return ProcessingResult(
            success=False,
            item_id=item_id,
            error=str(e)
        )


async def _record_processing_event(
    db: AsyncSession,
    item_id: str,
    from_status: ItemStatus,
    to_status: ItemStatus,
    result: Dict[str, Any]
) -> None:
    """记录处理事件.

    Args:
        db: 数据库会话
        item_id: Item ID
        from_status: 处理前状态
        to_status: 处理后状态
        result: 处理结果数据
    """
    try:
        # 尝试导入 AgentProcessEvent 模型
        # 如果模型不存在，暂时跳过（后续会创建）
        from agent_os.agent.models import AgentProcessEvent

        # 处理 from_status 和 to_status - 可能是枚举或字符串
        from_status_val = from_status.value if hasattr(from_status, 'value') else str(from_status)
        to_status_val = to_status.value if hasattr(to_status, 'value') else str(to_status)

        event = AgentProcessEvent(
            item_id=item_id,
            from_status=from_status_val,
            to_status=to_status_val,
            result_summary=result,
            processed_at=datetime.utcnow()
        )

        db.add(event)
        # 注意：这里不提交，让调用者控制事务

    except ImportError:
        # 模型尚未创建，跳过记录
        logger.debug("AgentProcessEvent model not yet implemented, skipping event recording")
        pass


async def process_multiple_items(
    db: AsyncSession,
    item_ids: list[str],
    force_reprocess: bool = False,
    stop_on_error: bool = False
) -> list[ProcessingResult]:
    """批量处理多个 InboxItem.

    Args:
        db: 数据库会话
        item_ids: Item ID 列表
        force_reprocess: 是否强制重新处理
        stop_on_error: 是否在遇到错误时停止处理

    Returns:
        ProcessingResult 列表
    """
    results = []

    for item_id in item_ids:
        try:
            result = await process_inbox_item(db, item_id, force_reprocess)
            results.append(result)

            if not result.success and stop_on_error:
                logger.warning(f"Stopping processing due to error on item {item_id}")
                break

        except Exception as e:
            logger.error(f"Unexpected error processing item {item_id}: {str(e)}")
            result = ProcessingResult(
                success=False,
                item_id=item_id,
                error=str(e)
            )
            results.append(result)

            if stop_on_error:
                break

    return results


async def get_raw_items(db: AsyncSession, limit: int = 10) -> list[Item]:
    """获取待处理的 raw 状态的 Items.

    Args:
        db: 数据库会话
        limit: 最大返回数量

    Returns:
        Item 列表
    """
    from sqlalchemy import select

    # 查询 status='raw' 的 items
    stmt = select(Item).where(Item.status == ItemStatus.RAW).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return list(items)


async def agent_tick(
    db: AsyncSession,
    max_items: int = 10,
    force_reprocess: bool = False
) -> Dict[str, Any]:
    """执行一次 Agent Tick.

    处理所有 raw 状态的 InboxItems.

    Args:
        db: 数据库会话
        max_items: 最多处理多少个 item
        force_reprocess: 是否强制重新处理

    Returns:
        处理结果摘要
    """
    logger.info(f"Agent Tick started: max_items={max_items}, force_reprocess={force_reprocess}")

    # 1. 获取待处理 items
    raw_items = await get_raw_items(db, limit=max_items)

    if not raw_items:
        logger.info("No raw items to process")
        return {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "results": []
        }

    # 2. 处理每个 item
    item_ids = [str(item.id) for item in raw_items]
    results = await process_multiple_items(
        db,
        item_ids,
        force_reprocess=force_reprocess,
        stop_on_error=False  # 不因为单个错误而停止
    )

    # 3. 统计结果
    succeeded = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    skipped = sum(1 for r in results if r.success and r.metadata.get("skipped"))

    summary = {
        "processed": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "results": [r.to_dict() for r in results]
    }

    logger.info(f"Agent Tick completed: {succeeded} succeeded, {failed} failed, {skipped} skipped")

    return summary
