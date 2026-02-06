"""Insight CRUD Operations - Stage 5 Implementation.

CRUD operations for Insight items and extensions.
"""

import uuid
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from agent_os.items.models import Item
from agent_os.insights.models import InsightExtension, InsightCluster
from agent_os.items.crud import create_item, get_item
from agent_os.items.schema import ItemCreate

logger = logging.getLogger(__name__)


# ============================================================================
# Insight CRUD
# ============================================================================

async def create_insight(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    creator_id: uuid.UUID,
    claim: str,
    rationale: Optional[str] = None,
    implications: Optional[List[str]] = None,
    source_refs: Optional[List[str]] = None,
    area_id: Optional[uuid.UUID] = None
) -> InsightExtension:
    """
    创建 Insight

    Args:
        db: 数据库会话
        workspace_id: 工作空间 ID
        creator_id: 创建者 ID
        claim: 洞察陈述
        rationale: 推理过程
        implications: 启示列表
        source_refs: 来源 Item IDs
        area_id: 区域 ID

    Returns:
        创建的 InsightExtension 对象
    """
    from agent_os.insights.models import generate_claim_hash

    # 检查是否重复
    claim_hash = generate_claim_hash(claim)

    existing_result = await db.execute(
        select(InsightExtension).where(
            InsightExtension.claim_hash == claim_hash
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        raise ValueError(f"Insight with similar claim already exists: {existing.item_id}")

    # 构建 insight 内容
    content_parts = [f"## Claim\n{claim}"]
    if rationale:
        content_parts.append(f"\n## Rationale\n{rationale}")
    if implications:
        content_parts.append(f"\n## Implications")
        for i, implication in enumerate(implications, 1):
            content_parts.append(f"{i}. {implication}")

    insight_content = "\n".join(content_parts)

    # 创建 Item
    item_data = ItemCreate(
        workspace_id=workspace_id,
        creator_id=creator_id,
        type="insight",
        title=claim[:100],
        content=insight_content,
        summary=rationale,
        area_id=area_id
    )

    item = await create_item(db, item_data)

    # 创建 InsightExtension
    insight_extension = InsightExtension(
        item_id=item.id,
        claim=claim,
        rationale=rationale,
        implications=implications or [],
        claim_hash=claim_hash,
        source_refs=source_refs or [],
        confidence_score={"score": 0.75, "factors": ["manual_creation"]},
        mining_metadata={"trigger": "manual"},
        review_status="pending"
    )

    db.add(insight_extension)
    await db.commit()
    await db.refresh(insight_extension)

    return insight_extension


async def get_insight(
    db: AsyncSession,
    insight_id: uuid.UUID
) -> Optional[InsightExtension]:
    """
    获取 Insight

    Args:
        db: 数据库会话
        insight_id: Insight Item ID

    Returns:
        InsightExtension 对象，不存在返回 None
    """
    result = await db.execute(
        select(InsightExtension).where(
            InsightExtension.item_id == insight_id
        ).options(selectinload(InsightExtension.item))
    )
    return result.scalar_one_or_none()


async def list_insights(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    review_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[InsightExtension]:
    """
    列出 Insights

    Args:
        db: 数据库会话
        workspace_id: 工作空间 ID
        review_status: 审核状态过滤 (可选)
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        InsightExtension 列表
    """
    # 查询 items
    query = select(Item).where(
        and_(
            Item.workspace_id == workspace_id,
            Item.type == "insight"
        )
    )

    # 获取 item IDs
    result = await db.execute(query)
    items = result.scalars().all()
    item_ids = [item.id for item in items]

    if not item_ids:
        return []

    # 查询 insights
    query = select(InsightExtension).where(
        InsightExtension.item_id.in_(item_ids)
    )

    if review_status:
        query = query.where(InsightExtension.review_status == review_status)

    query = query.order_by(InsightExtension.created_at.desc())
    query = query.limit(limit).offset(offset)

    result = await db.execute(query.options(selectinload(InsightExtension.item)))
    return result.scalars().all()


async def update_insight_review(
    db: AsyncSession,
    insight_id: uuid.UUID,
    *,
    review_status: str,
    reviewed_by: uuid.UUID
) -> Optional[InsightExtension]:
    """
    更新 Insight 审核状态

    Args:
        db: 数据库会话
        insight_id: Insight Item ID
        review_status: 审核状态 ('approved', 'rejected')
        reviewed_by: 审核者 ID

    Returns:
        更新后的 InsightExtension，不存在返回 None
    """
    from datetime import datetime

    result = await db.execute(
        select(InsightExtension).where(
            InsightExtension.item_id == insight_id
        )
    )
    insight = result.scalar_one_or_none()

    if not insight:
        return None

    insight.review_status = review_status
    insight.reviewed_at = datetime.utcnow()
    insight.reviewed_by = reviewed_by

    await db.commit()
    await db.refresh(insight)

    return insight


async def delete_insight(
    db: AsyncSession,
    insight_id: uuid.UUID
) -> bool:
    """
    删除 Insight (软删除)

    Args:
        db: 数据库会话
        insight_id: Insight Item ID

    Returns:
        是否删除成功
    """
    result = await db.execute(
        select(Item).where(Item.id == insight_id)
    )
    item = result.scalar_one_or_none()

    if not item:
        return False

    # 软删除: 更新状态为 archived
    item.status = "archived"
    await db.commit()

    return True


async def get_insights_by_source(
    db: AsyncSession,
    source_item_id: uuid.UUID,
    limit: int = 20
) -> List[InsightExtension]:
    """
    查询引用了某个来源 Item 的 Insights

    Args:
        db: 数据库会话
        source_item_id: 来源 Item ID
        limit: 返回数量限制

    Returns:
        InsightExtension 列表
    """
    source_id_str = str(source_item_id)

    query = select(InsightExtension).where(
        InsightExtension.source_refs.contains(source_id_str)
    ).options(selectinload(InsightExtension.item)).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def get_insight_stats(
    db: AsyncSession,
    workspace_id: uuid.UUID
) -> Dict[str, Any]:
    """
    获取 Insight 统计信息

    Args:
        db: 数据库会话
        workspace_id: 工作空间 ID

    Returns:
        统计信息字典
    """
    # 获取 workspace 中的所有 insight items
    item_result = await db.execute(
        select(Item.id).where(
            and_(
                Item.workspace_id == workspace_id,
                Item.type == "insight"
            )
        )
    )
    item_ids = [row[0] for row in item_result.all()]

    if not item_ids:
        return {
            "total_insights": 0,
            "by_status": {},
            "recent_insights": []
        }

    # 总数
    total_result = await db.execute(
        select(func.count(InsightExtension.id)).where(
            InsightExtension.item_id.in_(item_ids)
        )
    )
    total = total_result.scalar_one_or_none() or 0

    # 按状态统计
    status_result = await db.execute(
        select(
            InsightExtension.review_status,
            func.count(InsightExtension.id)
        ).where(
            InsightExtension.item_id.in_(item_ids)
        ).group_by(InsightExtension.review_status)
    )
    by_status = {row[0]: row[1] for row in status_result.all()}

    # 最近的 insights
    recent_result = await db.execute(
        select(InsightExtension).where(
            InsightExtension.item_id.in_(item_ids)
        ).order_by(
            InsightExtension.created_at.desc()
        ).limit(5).options(selectinload(InsightExtension.item))
    )
    recent_insights = recent_result.scalars().all()

    return {
        "total_insights": total,
        "by_status": by_status,
        "recent_insights": [
            {
                "id": str(insight.item_id),
                "claim": insight.claim,
                "review_status": insight.review_status,
                "created_at": insight.created_at.isoformat()
            }
            for insight in recent_insights
        ]
    }


# ============================================================================
# Insight Cluster CRUD
# ============================================================================

async def create_insight_cluster(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    item_ids: List[uuid.UUID],
    cluster_type: str = "strong_connection"
) -> InsightCluster:
    """
    创建挖掘集群

    Args:
        db: 数据库会话
        workspace_id: 工作空间 ID
        item_ids: Item ID 列表
        cluster_type: 集群类型

    Returns:
        创建的 InsightCluster 对象
    """
    cluster = InsightCluster(
        workspace_id=workspace_id,
        cluster_type=cluster_type,
        item_ids=[str(item_id) for item_id in item_ids],
        cluster_score={"size": len(item_ids)},
        mining_status="pending"
    )

    db.add(cluster)
    await db.commit()
    await db.refresh(cluster)

    return cluster


async def get_pending_clusters(
    db: AsyncSession,
    workspace_id: Optional[uuid.UUID] = None,
    limit: int = 50
) -> List[InsightCluster]:
    """
    获取待挖掘的集群

    Args:
        db: 数据库会话
        workspace_id: 工作空间 ID (可选)
        limit: 返回数量限制

    Returns:
        InsightCluster 列表
    """
    query = select(InsightCluster).where(
        InsightCluster.mining_status == "pending"
    )

    if workspace_id:
        query = query.where(InsightCluster.workspace_id == workspace_id)

    query = query.order_by(InsightCluster.created_at.asc()).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def update_cluster_status(
    db: AsyncSession,
    cluster_id: uuid.UUID,
    *,
    mining_status: str,
    insight_id: Optional[uuid.UUID] = None,
    error_message: Optional[str] = None
) -> Optional[InsightCluster]:
    """
    更新集群状态

    Args:
        db: 数据库会话
        cluster_id: 集群 ID
        mining_status: 挖掘状态
        insight_id: 生成的 Insight ID (可选)
        error_message: 错误信息 (可选)

    Returns:
        更新后的集群对象
    """
    result = await db.execute(
        select(InsightCluster).where(InsightCluster.id == cluster_id)
    )
    cluster = result.scalar_one_or_none()

    if not cluster:
        return None

    cluster.mining_status = mining_status
    if insight_id:
        cluster.insight_id = insight_id
    if error_message:
        cluster.error_message = error_message

    await db.commit()
    await db.refresh(cluster)

    return cluster
