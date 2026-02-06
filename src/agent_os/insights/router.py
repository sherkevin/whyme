"""Insights API Router - Insight Mining Endpoints."""

import uuid
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException

from agent_os.insights.miner import InsightMiner, LLMClient, mine_insight_from_items
from agent_os.insights import crud
from agent_os.insights.schema import (
    InsightCreate,
    InsightResponse,
    InsightList,
    InsightReviewRequest,
    MineInsightRequest,
    MineInsightResponse,
    FindClustersRequest,
    FindClustersResponse,
    ClusterInfo,
    InsightStats,
    HealthResponse
)
from agent_os.db.base import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])


# ============================================================================
# Insight CRUD Endpoints
# ============================================================================

@router.post("", response_model=InsightResponse)
async def create_insight(
    request: InsightCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建 Insight

    Args:
        request: 创建请求
        db: 数据库会话

    Returns:
        创建的 Insight
    """
    try:
        # 验证 UUID 格式
        workspace_id = uuid.UUID(request.workspace_id)
        creator_id = uuid.UUID(request.creator_id)

        area_id = None
        if request.area_id:
            area_id = uuid.UUID(request.area_id)

        insight = await crud.create_insight(
            db,
            workspace_id=workspace_id,
            creator_id=creator_id,
            claim=request.claim,
            rationale=request.rationale,
            implications=request.implications,
            source_refs=request.source_refs,
            area_id=area_id
        )

        return InsightResponse(
            id=str(insight.item_id),
            claim=insight.claim,
            rationale=insight.rationale,
            implications=insight.implications,
            claim_hash=insight.claim_hash,
            source_refs=insight.source_refs,
            confidence_score=insight.confidence_score,
            review_status=insight.review_status,
            created_at=insight.created_at
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=InsightList)
async def list_insights(
    workspace_id: str,
    review_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    列出 Insights

    Args:
        workspace_id: 工作空间 ID
        review_status: 审核状态过滤 (可选)
        limit: 返回数量限制
        offset: 偏移量
        db: 数据库会话

    Returns:
        Insight 列表
    """
    try:
        workspace_uuid = uuid.UUID(workspace_id)

        insights = await crud.list_insights(
            db,
            workspace_id=workspace_uuid,
            review_status=review_status,
            limit=limit,
            offset=offset
        )

        # 获取总数
        from sqlalchemy import select, func, and_
        from agent_os.items.models import Item

        count_result = await db.execute(
            select(func.count(Item.id)).where(
                and_(
                    Item.workspace_id == workspace_uuid,
                    Item.type == "insight"
                )
            )
        )
        total = count_result.scalar_one_or_none() or 0

        return InsightList(
            insights=[
                InsightResponse(
                    id=str(insight.item_id),
                    claim=insight.claim,
                    rationale=insight.rationale,
                    implications=insight.implications,
                    claim_hash=insight.claim_hash,
                    source_refs=insight.source_refs,
                    confidence_score=insight.confidence_score,
                    review_status=insight.review_status,
                    created_at=insight.created_at
                )
                for insight in insights
            ],
            total=total,
            limit=limit,
            offset=offset
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {e}")
    except Exception as e:
        logger.error(f"Error listing insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{insight_id}", response_model=InsightResponse)
async def get_insight(
    insight_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取单个 Insight

    Args:
        insight_id: Insight Item ID
        db: 数据库会话

    Returns:
        Insight 详情
    """
    try:
        insight_uuid = uuid.UUID(insight_id)
        insight = await crud.get_insight(db, insight_uuid)

        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")

        return InsightResponse(
            id=str(insight.item_id),
            claim=insight.claim,
            rationale=insight.rationale,
            implications=insight.implications,
            claim_hash=insight.claim_hash,
            source_refs=insight.source_refs,
            confidence_score=insight.confidence_score,
            review_status=insight.review_status,
            created_at=insight.created_at
        )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid insight ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{insight_id}/review", response_model=InsightResponse)
async def review_insight(
    insight_id: str,
    request: InsightReviewRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    审核 Insight

    Args:
        insight_id: Insight Item ID
        request: 审核请求
        db: 数据库会话

    Returns:
        更新后的 Insight
    """
    try:
        insight_uuid = uuid.UUID(insight_id)
        reviewed_by_uuid = uuid.UUID(request.reviewed_by)

        if request.review_status not in ["approved", "rejected"]:
            raise HTTPException(
                status_code=400,
                detail="review_status must be 'approved' or 'rejected'"
            )

        insight = await crud.update_insight_review(
            db,
            insight_uuid,
            review_status=request.review_status,
            reviewed_by=reviewed_by_uuid
        )

        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")

        return InsightResponse(
            id=str(insight.item_id),
            claim=insight.claim,
            rationale=insight.rationale,
            implications=insight.implications,
            claim_hash=insight.claim_hash,
            source_refs=insight.source_refs,
            confidence_score=insight.confidence_score,
            review_status=insight.review_status,
            created_at=insight.created_at
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reviewing insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{insight_id}")
async def delete_insight(
    insight_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    删除 Insight (软删除)

    Args:
        insight_id: Insight Item ID
        db: 数据库会话

    Returns:
        删除结果
    """
    try:
        insight_uuid = uuid.UUID(insight_id)
        success = await crud.delete_insight(db, insight_uuid)

        if not success:
            raise HTTPException(status_code=404, detail="Insight not found")

        return {"status": "deleted", "insight_id": insight_id}

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid insight ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Insight Mining Endpoints
# ============================================================================

@router.post("/mine", response_model=MineInsightResponse)
async def mine_insight(
    request: MineInsightRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    从 Item 集群挖掘 Insight

    Args:
        request: 挖掘请求
        db: 数据库会话

    Returns:
        挖掘结果
    """
    try:
        # 验证 UUID 格式
        workspace_id = uuid.UUID(request.workspace_id)
        item_ids = [uuid.UUID(id_str) for id_str in request.item_ids]

        if len(item_ids) < 3:
            raise HTTPException(
                status_code=400,
                detail="At least 3 items required for mining"
            )

        # 挖掘 insight
        result = await mine_insight_from_items(
            db,
            item_ids,
            workspace_id
        )

        return MineInsightResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error mining insight: {e}")
        return MineInsightResponse(
            status="error",
            error=str(e)
        )


@router.post("/find-clusters", response_model=FindClustersResponse)
async def find_clusters(
    request: FindClustersRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    查找高密度连接集群

    Args:
        request: 查找请求
        db: 数据库会话

    Returns:
        集群列表
    """
    try:
        workspace_id = uuid.UUID(request.workspace_id)

        miner = InsightMiner(
            min_cluster_size=request.min_cluster_size,
            min_connection_weight=request.min_connection_weight
        )

        # 查找集群
        clusters = await miner.find_high_density_clusters(
            db,
            workspace_id,
            min_cluster_size=request.min_cluster_size,
            min_connection_weight=request.min_connection_weight
        )

        # 为每个集群创建 Cluster 对象
        cluster_infos = []
        for item_ids in clusters:
            cluster = await crud.create_insight_cluster(
                db,
                workspace_id=workspace_id,
                item_ids=item_ids,
                cluster_type="strong_connection"
            )
            cluster_infos.append(
                ClusterInfo(
                    id=str(cluster.id),
                    cluster_type=cluster.cluster_type,
                    item_ids=cluster.item_ids,
                    mining_status=cluster.mining_status,
                    created_at=cluster.created_at
                )
            )

        return FindClustersResponse(
            clusters=cluster_infos,
            total=len(cluster_infos)
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error finding clusters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Stats Endpoints
# ============================================================================

@router.get("/stats/workspace/{workspace_id}", response_model=InsightStats)
async def get_insight_stats(
    workspace_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取 Insight 统计信息

    Args:
        workspace_id: 工作空间 ID
        db: 数据库会话

    Returns:
        统计信息
    """
    try:
        workspace_uuid = uuid.UUID(workspace_id)

        stats = await crud.get_insight_stats(db, workspace_uuid)

        return InsightStats(**stats)

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid workspace ID format")
    except Exception as e:
        logger.error(f"Error getting insight stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Health Endpoints
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def insights_health():
    """
    Insights 服务健康检查

    Returns:
        健康状态
    """
    return HealthResponse(
        status="healthy",
        service="insights-mining"
    )
