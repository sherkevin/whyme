"""Connection API Router - Cognitive Graph Endpoints."""

import uuid
import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException

from agent_os.connections.engine import ConnectionEngine
from agent_os.connections import crud
from agent_os.connections.schema import (
    ConnectionList,
    ConnectionStats,
    GraphData,
    RecalculateRequest,
    RecalculateResponse
)
from agent_os.items.models import Item, GraphEdge
from agent_os.db.base import get_db
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["connections"])


# ============================================================================
# Connection Query Endpoints
# ============================================================================

@router.get("/{node_id}", response_model=ConnectionList)
async def get_connections(
    node_id: uuid.UUID,
    strong_only: bool = False,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    查询节点的所有连接

    Args:
        node_id: 节点ID
        strong_only: 是否只查询强连接
        limit: 返回数量限制

    Returns:
        连接列表
    """
    try:
        # 转换node_id
        try:
            node_uuid = uuid.UUID(str(node_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid node_id format")

        # 验证node存在
        result = await db.execute(
            select(Item).where(Item.id == node_uuid)
        )
        node = result.scalar_one_or_none()

        if not node:
            raise HTTPException(status_code=404, detail="Node not found")

        # 获取连接
        edges = await crud.get_connections(
            db,
            node_uuid,
            strong_only=strong_only,
            limit=limit
        )

        # 获取统计
        stats = await crud.get_connection_stats(db, node_uuid)

        # 转换为响应格式
        connection_list = ConnectionList(
            node_id=node_uuid,
            connections=edges,
            total_count=stats["total_connections"],
            strong_count=stats["strong_connections"]
        )

        return connection_list

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting connections for node {node_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{node_id}/strong", response_model=ConnectionList)
async def get_strong_connections(
    node_id: uuid.UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    查询节点的强连接

    Args:
        node_id: 节点ID
        limit: 返回数量限制

    Returns:
        强连接列表
    """
    try:
        node_uuid = uuid.UUID(str(node_id))

        # 验证node存在
        result = await db.execute(
            select(Item).where(Item.id == node_uuid)
        )
        node = result.scalar_one_or_none()

        if not node:
            raise HTTPException(status_code=404, detail="Node not found")

        # 获取强连接
        edges = await crud.get_strong_connections(
            db,
            node_uuid,
            limit=limit
        )

        stats = await crud.get_connection_stats(db, node_uuid)

        return ConnectionList(
            node_id=node_uuid,
            connections=edges,
            total_count=stats["total_connections"],
            strong_count=stats["strong_connections"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strong connections for node {node_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{node_id}/stats", response_model=ConnectionStats)
async def get_connection_statistics(
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    获取节点的连接统计信息

    Args:
        node_id: 节点ID

    Returns:
        连接统计
    """
    try:
        node_uuid = uuid.UUID(str(node_id))

        stats = await crud.get_connection_stats(db, node_uuid)

        return ConnectionStats(**stats)

    except Exception as e:
        logger.error(f"Error getting connection stats for node {node_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{node_id}/graph", response_model=GraphData)
async def get_connection_graph(
    node_id: uuid.UUID,
    depth: int = 1,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    获取节点的连接图数据 (用于可视化)

    Args:
        node_id: 中心节点ID
        depth: 图深度 (目前只支持depth=1)
        limit: 每层节点数量限制

    Returns:
        图数据 (节点和边)
    """
    try:
        if depth != 1:
            raise HTTPException(status_code=400, detail="Only depth=1 is supported currently")

        node_uuid = uuid.UUID(str(node_id))

        # 验证中心节点存在
        result = await db.execute(
            select(Item).where(Item.id == node_uuid)
        )
        center_node = result.scalar_one_or_none()

        if not center_node:
            raise HTTPException(status_code=404, detail="Node not found")

        # 获取连接
        edges = await crud.get_connections(
            db,
            node_uuid,
            strong_only=False,
            limit=limit
        )

        # 收集所有相关节点ID
        node_ids = {node_uuid}
        for edge in edges:
            node_ids.add(edge.from_node_id)
            node_ids.add(edge.to_node_id)

        # 查询节点信息
        from agent_os.connections.schema import GraphNode
        nodes_data = []

        for nid in node_ids:
            result = await db.execute(
                select(Item).where(Item.id == nid)
            )
            item = result.scalar_one_or_none()

            if item:
                nodes_data.append(GraphNode(
                    id=item.id,
                    label=item.title or item.content[:50] if item.content else "",
                    type=item.type,
                    created_at=item.created_at.isoformat() if item.created_at else None
                ))

        # 转换边
        from agent_os.connections.schema import GraphEdgeSimple
        edges_data = [
            GraphEdgeSimple(
                from_node=edge.from_node_id,
                to_node=edge.to_node_id,
                weight=edge.weight,
                relation_type=edge.relation_type,
                is_strong=edge.is_strong
            )
            for edge in edges
        ]

        return GraphData(
            nodes=nodes_data,
            edges=edges_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting graph data for node {node_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Connection Calculation Endpoints
# ============================================================================

@router.post("/recalculate", response_model=RecalculateResponse)
async def recalculate_connections(
    request: RecalculateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    手动触发连接计算

    为指定Item计算与同workspace内其他Item的连接

    Args:
        request: 重新计算请求

    Returns:
        计算结果
    """
    try:
        item_id = uuid.UUID(str(request.item_id))

        # 验证Item存在
        result = await db.execute(
            select(Item).where(Item.id == item_id)
        )
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        # 查询候选Items (同workspace, 最近30天更新)
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=30)

        candidates_result = await db.execute(
            select(Item).where(
                and_(
                    Item.workspace_id == item.workspace_id,
                    Item.id != item_id,
                    Item.updated_at >= cutoff_date,
                    Item.status == "active"
                )
            ).limit(request.limit)
        )
        candidates = candidates_result.scalars().all()

        if not candidates:
            return RecalculateResponse(
                item_id=item_id,
                connections_created=0,
                connections_updated=0,
                message="No candidate items found"
            )

        # 批量计算连接
        engine = ConnectionEngine()
        created = 0
        updated = 0

        for candidate in candidates:
            edge = await crud.calculate_and_store_connection(
                db,
                item_id,
                candidate.id,
                engine
            )

            if edge:
                # 检查是新创建还是更新
                if edge.created_at == edge.created_at:  # 简化判断
                    created += 1
                else:
                    updated += 1

        return RecalculateResponse(
            item_id=item_id,
            connections_created=created,
            connections_updated=updated,
            message=f"Processed {len(candidates)} candidates"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recalculating connections for item {request.item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Health Check
# ============================================================================

@router.get("/graph/all", response_model=GraphData)
async def get_full_graph(
    limit: int = 50,
    min_score: float = 0.0,
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户的完整知识图谱数据（用于数字花园可视化）

    Args:
        limit: 节点数上限
        min_score: 最低关联分数阈值

    Returns:
        完整图数据 (所有节点和边)
    """
    try:
        from agent_os.connections.schema import GraphNode, GraphEdgeSimple

        # 获取所有有连接的边
        from sqlalchemy import desc
        query = select(GraphEdge).order_by(desc(GraphEdge.weight))
        if min_score > 0:
            query = query.where(GraphEdge.weight >= min_score)
        query = query.limit(limit * 5)  # 边数量可以多一些

        result = await db.execute(query)
        edges = result.scalars().all()

        # 收集所有节点ID
        node_ids = set()
        for edge in edges:
            node_ids.add(edge.from_node_id)
            node_ids.add(edge.to_node_id)

        # 限制节点数量
        node_ids = list(node_ids)[:limit]

        # 查询节点信息
        nodes_data = []
        node_connection_count = {}

        for edge in edges:
            for nid in [edge.from_node_id, edge.to_node_id]:
                node_connection_count[nid] = node_connection_count.get(nid, 0) + 1

        from agent_os.knowledge.models import Card
        for nid in node_ids:
            result = await db.execute(
                select(Item).where(Item.id == nid)
            )
            item = result.scalar_one_or_none()
            
            if item:
                nodes_data.append(GraphNode(
                    id=item.id,
                    label=item.title or (item.content[:50] if item.content else ""),
                    type=item.type or "note",
                    created_at=item.created_at.isoformat() if item.created_at else None
                ))
            else:
                # Fallback: 查 cards 表
                card_result = await db.execute(
                    select(Card).where(Card.id == nid)
                )
                card = card_result.scalar_one_or_none()
                if card:
                    nodes_data.append(GraphNode(
                        id=card.id,
                        label=card.title or (card.content[:50] if card.content else ""),
                        type="card",
                        created_at=card.created_at.isoformat() if card.created_at else None
                    ))


        # 过滤边（只保留两端都在节点集中的边）
        node_id_set = {n.id for n in nodes_data}
        edges_data = [
            GraphEdgeSimple(
                from_node=edge.from_node_id,
                to_node=edge.to_node_id,
                weight=edge.weight,
                relation_type=edge.relation_type,
                is_strong=edge.is_strong
            )
            for edge in edges
            if edge.from_node_id in node_id_set and edge.to_node_id in node_id_set
        ]

        return GraphData(
            nodes=nodes_data,
            edges=edges_data
        )

    except Exception as e:
        logger.error(f"Error getting full graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=RecalculateResponse)
async def generate_all_connections(
    force: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    手动触发全量关联生成

    Args:
        force: 是否清除旧关联重新生成

    Returns:
        生成结果
    """
    try:
        from datetime import datetime, timedelta

        # 如果force，先清除所有边
        if force:
            from sqlalchemy import delete as sql_delete
            await db.execute(sql_delete(GraphEdge))
            await db.commit()

        # 获取所有活跃Items
        # 获取所有活跃Items
        items_result = await db.execute(
            select(Item).where(Item.status == "active").limit(200)
        )
        items = items_result.scalars().all()

        # 同时获取 cards 表的数据，转为伪 Item 对象参与计算
        from agent_os.knowledge.models import Card
        cards_result = await db.execute(select(Card).limit(200))
        cards = cards_result.scalars().all()
        
        # 将 Card 包装为兼容 Item 的对象
        class CardAsItem:
            def __init__(self, card):
                self.id = card.id
                self.title = card.title
                self.content = card.content
                self.embedding = None
                self.area_id = None
                self.workspace_id = card.workspace_id
                self.type = "card"
                self.status = "active"
                self.updated_at = card.updated_at or card.created_at
                self.created_at = card.created_at
        
        card_items = [CardAsItem(c) for c in cards]
        items = list(items) + card_items


        if not items:
            return RecalculateResponse(
                item_id=uuid.UUID('00000000-0000-0000-0000-000000000000'),
                connections_created=0,
                connections_updated=0,
                message="No items found"
            )

        engine = ConnectionEngine()
        created = 0

        # 两两计算
        for i, item_a in enumerate(items):
            for item_b in items[i+1:]:
                edge = await crud.calculate_and_store_connection(
                    db, item_a.id, item_b.id, engine,
                    item_a_obj=item_a, item_b_obj=item_b
                )
                if edge:
                    created += 1

        return RecalculateResponse(
            item_id=items[0].id,
            connections_created=created,
            connections_updated=0,
            message=f"Generated {created} relations from {len(items)} items"
        )

    except Exception as e:
        logger.error(f"Error generating connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "connection-engine",
        "version": "stage-3"
    }
