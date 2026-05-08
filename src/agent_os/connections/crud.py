"""Connection CRUD Operations - Graph Edges Management."""

import uuid
from typing import List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.connections.engine import ConnectionEngine
from agent_os.items.models import GraphEdge, Item

# ============================================================================
# Connection CRUD
# ============================================================================

async def create_connection(
    db: AsyncSession,
    *,
    from_node_id: uuid.UUID,
    to_node_id: uuid.UUID,
    weight: float,
    relation_type: str,
    is_strong: bool = False
) -> GraphEdge:
    """
    创建连接 (GraphEdge)

    Args:
        db: 数据库会话
        from_node_id: 源节点ID
        to_node_id: 目标节点ID
        weight: 连接权重 (0.0 - 1.0)
        relation_type: 关系类型 ('topic', 'causal', 'supplement')
        is_strong: 是否为强连接

    Returns:
        创建的GraphEdge对象
    """
    edge = GraphEdge(
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        weight=weight,
        relation_type=relation_type,
        is_strong=is_strong
    )

    db.add(edge)
    await db.commit()
    await db.refresh(edge)

    return edge


async def get_connections(
    db: AsyncSession,
    node_id: uuid.UUID,
    *,
    strong_only: bool = False,
    limit: int = 100
) -> list[GraphEdge]:
    """
    查询节点的所有连接

    Args:
        db: 数据库会话
        node_id: 节点ID
        strong_only: 是否只查询强连接
        limit: 返回数量限制

    Returns:
        GraphEdge列表
    """
    # 查询出边 (from_node_id = node_id)
    from sqlalchemy import desc

    query_out = select(GraphEdge).where(
        GraphEdge.from_node_id == node_id
    )

    # 查询入边 (to_node_id = node_id)
    query_in = select(GraphEdge).where(
        GraphEdge.to_node_id == node_id
    )

    # 应用强连接过滤
    if strong_only:
        query_out = query_out.where(GraphEdge.is_strong == True)
        query_in = query_in.where(GraphEdge.is_strong == True)

    # 排序并限制
    query_out = query_out.order_by(desc(GraphEdge.weight)).limit(limit)
    query_in = query_in.order_by(desc(GraphEdge.weight)).limit(limit)

    # 执行查询
    result_out = await db.execute(query_out)
    result_in = await db.execute(query_in)

    edges_out = result_out.scalars().all()
    edges_in = result_in.scalars().all()

    # 合并去重
    all_edges = list(set(edges_out + edges_in))

    # 按权重排序
    all_edges.sort(key=lambda e: e.weight, reverse=True)

    return all_edges[:limit]


async def get_strong_connections(
    db: AsyncSession,
    node_id: uuid.UUID,
    limit: int = 50
) -> list[GraphEdge]:
    """
    查询节点的强连接

    Args:
        db: 数据库会话
        node_id: 节点ID
        limit: 返回数量限制

    Returns:
        强连接GraphEdge列表
    """
    return await get_connections(
        db,
        node_id,
        strong_only=True,
        limit=limit
    )


async def delete_connection(
    db: AsyncSession,
    edge_id: uuid.UUID
) -> bool:
    """
    删除连接

    Args:
        db: 数据库会话
        edge_id: 边ID

    Returns:
        是否删除成功
    """
    from sqlalchemy import delete

    result = await db.execute(
        delete(GraphEdge).where(GraphEdge.id == edge_id)
    )

    await db.commit()

    return result.rowcount > 0


async def calculate_and_store_connection(
    db: AsyncSession,
    item_a_id: uuid.UUID,
    item_b_id: uuid.UUID,
    engine: ConnectionEngine | None = None
) -> GraphEdge | None:
    """
    计算两个Item之间的连接并存储

    Args:
        db: 数据库会话
        item_a_id: Item A ID
        item_b_id: Item B ID
        engine: 连接引擎 (可选)

    Returns:
        创建的GraphEdge，如果分数太低则返回None
    """
    # 获取Items
    result_a = await db.execute(
        select(Item).where(Item.id == item_a_id)
    )
    item_a = result_a.scalar_one_or_none()

    result_b = await db.execute(
        select(Item).where(Item.id == item_b_id)
    )
    item_b = result_b.scalar_one_or_none()

    if not item_a or not item_b:
        return None

    # 创建引擎
    if engine is None:
        engine = ConnectionEngine()

    # 计算连接分数
    score = await engine.calculate_score(item_a, item_b)

    # 如果分数太低，不创建连接
    if score < 0.1:  # 降低阈值到0.1以适应没有embedding的情况
        return None

    # 判断关系类型和是否强连接
    relation_type = engine.get_relation_type(score)
    is_strong = engine.is_strong_connection(score)

    # 检查是否已存在
    existing = await db.execute(
        select(GraphEdge).where(
            and_(
                GraphEdge.from_node_id == item_a_id,
                GraphEdge.to_node_id == item_b_id
            )
        )
    )
    existing_edge = existing.scalar_one_or_none()

    if existing_edge:
        # 更新已存在的连接
        existing_edge.weight = score
        existing_edge.relation_type = relation_type
        existing_edge.is_strong = is_strong
        await db.commit()
        await db.refresh(existing_edge)
        return existing_edge

    # 创建新连接
    edge = await create_connection(
        db,
        from_node_id=item_a_id,
        to_node_id=item_b_id,
        weight=score,
        relation_type=relation_type,
        is_strong=is_strong
    )

    return edge


async def batch_calculate_connections(
    db: AsyncSession,
    item_id: uuid.UUID,
    candidate_ids: list[uuid.UUID],
    engine: ConnectionEngine | None = None
) -> list[GraphEdge]:
    """
    批量计算一个Item与多个候选Item的连接

    Args:
        db: 数据库会话
        item_id: 源Item ID
        candidate_ids: 候选Item ID列表
        engine: 连接引擎 (可选)

    Returns:
        创建的GraphEdge列表
    """
    if engine is None:
        engine = ConnectionEngine()

    edges = []

    for candidate_id in candidate_ids:
        # 避免自连接
        if candidate_id == item_id:
            continue

        edge = await calculate_and_store_connection(
            db,
            item_id,
            candidate_id,
            engine
        )

        if edge:
            edges.append(edge)

    return edges


async def get_connection_stats(
    db: AsyncSession,
    node_id: uuid.UUID
) -> dict:
    """
    获取节点的连接统计信息

    Args:
        db: 数据库会话
        node_id: 节点ID

    Returns:
        统计信息字典
    """
    # 总连接数 (出边 + 入边)
    total_out = await db.execute(
        select(func.count(GraphEdge.id)).where(
            GraphEdge.from_node_id == node_id
        )
    )
    total_in = await db.execute(
        select(func.count(GraphEdge.id)).where(
            GraphEdge.to_node_id == node_id
        )
    )

    # 强连接数
    strong_out = await db.execute(
        select(func.count(GraphEdge.id)).where(
            and_(
                GraphEdge.from_node_id == node_id,
                GraphEdge.is_strong == True
            )
        )
    )
    strong_in = await db.execute(
        select(func.count(GraphEdge.id)).where(
            and_(
                GraphEdge.to_node_id == node_id,
                GraphEdge.is_strong == True
            )
        )
    )

    # 按类型统计
    by_type_out = await db.execute(
        select(
            GraphEdge.relation_type,
            func.count(GraphEdge.id)
        ).where(
            GraphEdge.from_node_id == node_id
        ).group_by(GraphEdge.relation_type)
    )
    type_stats_result = by_type_out.all()
    type_stats = dict(type_stats_result) if type_stats_result else {}

    # 立即获取所有标量结果
    total_out_val = total_out.scalar_one_or_none() or 0
    total_in_val = total_in.scalar_one_or_none() or 0
    strong_out_val = strong_out.scalar_one_or_none() or 0
    strong_in_val = strong_in.scalar_one_or_none() or 0

    return {
        "total_connections": total_out_val + total_in_val,
        "outgoing_connections": total_out_val,
        "incoming_connections": total_in_val,
        "strong_connections": strong_out_val + strong_in_val,
        "by_type": type_stats
    }
