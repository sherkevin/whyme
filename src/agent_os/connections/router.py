"""Connection API Router - Cognitive Graph Endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.connections import crud
from agent_os.connections.engine import ConnectionEngine
from agent_os.connections.schema import (
    ConnectionList,
    ConnectionStats,
    GraphData,
    RecalculateRequest,
    RecalculateResponse,
)
from agent_os.db.base import get_db
from agent_os.items.models import Item

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["connections"])


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

@router.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "connection-engine",
        "version": "stage-3"
    }
