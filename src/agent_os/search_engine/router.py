"""FastAPI router for Stage 4 - Search, Ingestion, and Insight."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import time

from agent_os.db.base import get_db
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User

# Import services
from agent_os.search_engine.search_service import SearchService
from agent_os.search_engine.search_engine import SearchEngine, SearchQuery

# Import schemas
from agent_os.search_engine.schema import (
    # Search schemas
    SearchIndexCreate,
    SearchIndexUpdate,
    SearchIndexResponse,
    SearchQueryRequest,
    SearchResultItemResponse,
    SearchResponse,
    BulkIndexRequest,
    BulkIndexResponse,
    RebuildIndexResponse,
    # Ingestion schemas
    IngestionJobCreate,
    IngestionJobResponse,
    IngestionJobListResponse,
    # Insight schemas
    InsightClusterCreate,
    InsightClusterResponse,
    InsightClusterListResponse
)

# Import models
from agent_os.search_engine.models import SearchIndex, IngestionJob, InsightCluster
from sqlalchemy import select, func
import uuid as uuid_pkg

# =============================================================================
# Router Setup
# =============================================================================

router = APIRouter(prefix="/api/v1/search", tags=["search"])


# =============================================================================
# Search Index Management Endpoints
# =============================================================================

@router.post("/index", response_model=SearchIndexResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_search_index(
    request: SearchIndexCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update a search index entry.

    Args:
        request: Search index data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created/updated search index
    """
    service = SearchService(db)

    # Convert item_id to UUID
    try:
        item_uuid = uuid_pkg.UUID(request.item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item_id format")

    index = await service.index_item(
        item_type=request.item_type,
        item_id=item_uuid,
        title=request.title,
        content=request.content,
        tags=request.tags,
        search_metadata=request.search_metadata,
        embedding=request.embedding
    )

    return SearchIndexResponse.model_validate(index)


@router.post("/index/bulk", response_model=BulkIndexResponse, status_code=status.HTTP_201_CREATED)
async def bulk_create_search_index(
    request: BulkIndexRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk create/update search index entries.

    Args:
        request: Bulk index request with items
        db: Database session
        current_user: Authenticated user

    Returns:
        Bulk operation results
    """
    service = SearchService(db)

    # Convert items to dict format
    items_dict = []
    for item in request.items:
        try:
            item_uuid = uuid_pkg.UUID(item.item_id)
            items_dict.append({
                "item_type": item.item_type,
                "item_id": item_uuid,
                "title": item.title,
                "content": item.content,
                "tags": item.tags,
                "search_metadata": item.search_metadata,
                "embedding": item.embedding
            })
        except ValueError:
            return BulkIndexResponse(
                indexed=0,
                failed=len(request.items),
                errors=[f"Invalid item_id format: {item.item_id}"]
            )

    indexed_count = await service.bulk_index_items(items_dict)

    return BulkIndexResponse(
        indexed=indexed_count,
        failed=len(request.items) - indexed_count,
        errors=[]  # Could track specific errors
    )


@router.put("/index/{item_type}/{item_id}", response_model=SearchIndexResponse)
async def update_search_index(
    item_type: str,
    item_id: str,
    request: SearchIndexUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a search index entry.

    Args:
        item_type: Type of item
        item_id: UUID of item
        request: Update data
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated search index
    """
    service = SearchService(db)

    try:
        item_uuid = uuid_pkg.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item_id format")

    # Get existing index
    index = await service.get_index(item_type, item_uuid)
    if not index:
        raise HTTPException(status_code=404, detail="Search index not found")

    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(index, field, value)

    await db.commit()
    await db.refresh(index)

    return SearchIndexResponse.model_validate(index)


@router.delete("/index/{item_type}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search_index(
    item_type: str,
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a search index entry.

    Args:
        item_type: Type of item
        item_id: UUID of item
        db: Database session
        current_user: Authenticated user

    Returns:
        204 No Content
    """
    service = SearchService(db)

    try:
        item_uuid = uuid_pkg.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item_id format")

    result = await service.delete_index(item_type, item_uuid)

    if not result:
        raise HTTPException(status_code=404, detail="Search index not found")


@router.post("/index/rebuild", response_model=RebuildIndexResponse)
async def rebuild_search_index(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Rebuild the entire search index from source data.

    Args:
        db: Database session
        current_user: Authenticated user

    Returns:
        Rebuild status
    """
    service = SearchService(db)

    start_time = time.time()

    # This would scan all cards, tasks, notes, etc. and rebuild index
    # For now, return a placeholder response
    # In production, this would be a background task
    total_indexed = await service.rebuild_index()

    duration = time.time() - start_time

    return RebuildIndexResponse(
        status="completed",
        message=f"Rebuilt search index with {total_indexed} items",
        total_indexed=total_indexed,
        duration_seconds=duration
    )


# =============================================================================
# Search Query Endpoints
# =============================================================================

@router.get("", response_model=SearchResponse)
async def search(
    query: str = Query(..., min_length=1, description="Search query"),
    item_types: Optional[List[str]] = Query(None, description="Filter by item types"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    date_from: Optional[datetime] = Query(None, description="Filter from date"),
    date_to: Optional[datetime] = Query(None, description="Filter to date"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    sort_by: str = Query("relevance", description="Sort by: relevance, date, -date"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute a search query.

    Args:
        query: Search query text
        item_types: Optional item type filter
        tags: Optional tag filter
        date_from: Optional start date filter
        date_to: Optional end date filter
        page: Page number
        page_size: Results per page
        sort_by: Sort method
        db: Database session
        current_user: Authenticated user

    Returns:
        Search results
    """
    engine = SearchEngine(db)

    # Build search query
    search_query = SearchQuery(
        query=query,
        item_types=item_types,
        tags=tags,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by
    )

    # Execute search
    result = await engine.search(search_query)

    # Convert to response format
    results_response = [
            SearchResultItemResponse.model_validate({
            "item_type": r.item_type,
            "item_id": r.item_id,
            "title": r.title,
            "content_snippet": r.content_snippet,
            "score": r.score,
            "tags": r.tags,
            "search_metadata": r.search_metadata,
            "created_at": r.created_at
        }) for r in result.results
    ]

    return SearchResponse(
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        results=results_response
    )


@router.post("/query", response_model=SearchResponse)
async def search_post(
    request: SearchQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Execute a search query via POST.

    Args:
        request: Search query request
        db: Database session
        current_user: Authenticated user

    Returns:
        Search results
    """
    engine = SearchEngine(db)

    # Build search query
    search_query = SearchQuery(
        query=request.query,
        item_types=request.item_types,
        tags=request.tags,
        date_from=request.date_from,
        date_to=request.date_to,
        page=request.page,
        page_size=request.page_size,
        sort_by=request.sort_by,
        include_vectors=request.include_vectors
    )

    # Execute search
    result = await engine.search(search_query)

    # Convert to response format
    from agent_os.search_engine.schema import SearchResultItemResponse

    results_response = [
        SearchResultItemResponse(
            item_type=r.item_type,
            item_id=r.item_id,
            title=r.title,
            content_snippet=r.content_snippet,
            score=r.score,
            tags=r.tags,
            search_metadata=r.search_metadata,
            created_at=r.created_at
        ) for r in result.results
    ]

    return SearchResponse(
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        results=results_response
    )


# =============================================================================
# Ingestion Job Endpoints
# =============================================================================

@router.post("/ingestion/jobs", response_model=IngestionJobResponse, status_code=status.HTTP_201_CREATED)
async def create_ingestion_job(
    request: IngestionJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new ingestion job.

    Args:
        request: Ingestion job data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created ingestion job
    """
    job = IngestionJob(
        source_type=request.source_type,
        source_url=request.source_url,
        source_file_path=request.source_file_path,
        chunk_size=request.chunk_size,
        overlap=request.overlap,
        created_by=str(current_user.id) if current_user else None
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # In production, would trigger background task to process job
    # For now, job is created in pending state

    return IngestionJobResponse.model_validate(job)


@router.get("/ingestion/jobs", response_model=IngestionJobListResponse)
async def list_ingestion_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List ingestion jobs.

    Args:
        status: Optional status filter
        limit: Max results
        offset: Pagination offset
        db: Database session
        current_user: Authenticated user

    Returns:
        List of ingestion jobs
    """
    query = select(IngestionJob)

    if status:
        query = query.where(IngestionJob.status == status)

    # Get total count
    count_query = select(func.count(IngestionJob.id))
    if status:
        count_query = count_query.where(IngestionJob.status == status)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get paginated results
    query = query.order_by(IngestionJob.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return IngestionJobListResponse(
        total=total,
        jobs=[IngestionJobResponse.model_validate(j) for j in jobs]
    )


@router.get("/ingestion/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get ingestion job details.

    Args:
        job_id: Job UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Ingestion job details
    """
    try:
        job_uuid = uuid_pkg.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    stmt = select(IngestionJob).where(IngestionJob.id == job_uuid)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Ingestion job not found")

    return IngestionJobResponse.model_validate(job)


@router.post("/ingestion/jobs/{job_id}/start", response_model=IngestionJobResponse)
async def start_ingestion_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Start an ingestion job.

    Args:
        job_id: Job UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated job
    """
    from agent_os.search_engine.ingestion_pipeline import IngestionService

    service = IngestionService(db)

    try:
        job = await service.start_job(job_id)
        return IngestionJobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Insight Cluster Endpoints
# =============================================================================

@router.post("/insights/generate", response_model=InsightClusterResponse, status_code=status.HTTP_201_CREATED)
async def generate_insight(
    cluster_type: str = Query(..., description="Type of insight: summary, trend, topic, pattern"),
    item_type: str = Query(..., description="Source item type to analyze"),
    item_ids: Optional[List[str]] = Query(None, description="Optional list of specific item IDs"),
    date_range: Optional[dict] = None,
    num_topics: int = Query(5, ge=1, le=20, description="Number of topics to extract"),
    group_by: str = Query("day", description="Time grouping for trend: day, week, month"),
    metric: str = Query("count", description="Metric for trend analysis"),
    pattern_type: str = Query("creation_time", description="Pattern type to detect"),
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate a new insight cluster.

    Args:
        cluster_type: Type of insight to generate
        item_type: Source item type
        item_ids: Optional specific item IDs
        date_range: Optional date range for filtering
        num_topics: Number of topics (for topic clustering)
        group_by: Time grouping (for trend analysis)
        metric: Metric to analyze (for trend)
        pattern_type: Pattern type (for pattern detection)
        name: Optional name for the insight
        db: Database session
        current_user: Authenticated user

    Returns:
        Generated insight cluster
    """
    from agent_os.search_engine.insight_service import InsightService

    service = InsightService(db)

    # Generate insight based on type
    if cluster_type == "summary":
        insight = await service.generate_summary(
            item_type=item_type,
            item_ids=item_ids,
            date_range=date_range,
            name=name,
            generated_by=str(current_user.id) if current_user else None
        )
    elif cluster_type == "trend":
        insight = await service.generate_trend(
            item_type=item_type,
            metric=metric,
            date_range=date_range,
            group_by=group_by,
            name=name,
            generated_by=str(current_user.id) if current_user else None
        )
    elif cluster_type == "topic":
        insight = await service.generate_topics(
            item_type=item_type,
            item_ids=item_ids,
            num_topics=num_topics,
            name=name,
            generated_by=str(current_user.id) if current_user else None
        )
    elif cluster_type == "pattern":
        insight = await service.generate_pattern(
            item_type=item_type,
            pattern_type=pattern_type,
            date_range=date_range,
            name=name,
            generated_by=str(current_user.id) if current_user else None
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cluster_type: {cluster_type}. Must be one of: summary, trend, topic, pattern"
        )

    return InsightClusterResponse.model_validate(insight)


@router.post("/insights", response_model=InsightClusterResponse, status_code=status.HTTP_201_CREATED)
async def create_insight_cluster(
    request: InsightClusterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new insight cluster.

    Args:
        request: Insight cluster data
        db: Database session
        current_user: Authenticated user

    Returns:
        Created insight cluster
    """
    insight = InsightCluster(
        cluster_type=request.cluster_type,
        name=request.name,
        description=request.description,
        source_item_type=request.source_item_type,
        source_item_ids=request.source_item_ids or [],
        date_range=request.date_range,
        insight_data=request.insight_data,
        confidence=request.confidence,
        sample_count=request.sample_count,
        parameters=request.parameters,
        generated_by=str(current_user.id) if current_user else None
    )

    db.add(insight)
    await db.commit()
    await db.refresh(insight)

    return InsightClusterResponse.model_validate(insight)


@router.get("/insights", response_model=InsightClusterListResponse)
async def list_insight_clusters(
    cluster_type: Optional[str] = Query(None, description="Filter by cluster type"),
    source_item_type: Optional[str] = Query(None, description="Filter by source item type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List insight clusters.

    Args:
        cluster_type: Optional cluster type filter
        source_item_type: Optional source item type filter
        limit: Max results
        offset: Pagination offset
        db: Database session
        current_user: Authenticated user

    Returns:
        List of insight clusters
    """
    query = select(InsightCluster)

    if cluster_type:
        query = query.where(InsightCluster.cluster_type == cluster_type)

    if source_item_type:
        query = query.where(InsightCluster.source_item_type == source_item_type)

    # Get total count
    count_query = select(func.count(InsightCluster.id))
    if cluster_type:
        count_query = count_query.where(InsightCluster.cluster_type == cluster_type)
    if source_item_type:
        count_query = count_query.where(InsightCluster.source_item_type == source_item_type)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get paginated results
    query = query.order_by(InsightCluster.generated_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    insights = result.scalars().all()

    return InsightClusterListResponse(
        total=total,
        insights=[InsightClusterResponse.model_validate(i) for i in insights]
    )


@router.post("/insights/deep-generate")
async def deep_generate_insights(
    force: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """
    基于知识图谱 Cluster 检测生成认知结晶

    Args:
        force: 是否清除旧 insight 重新生成
    """
    from agent_os.search_engine.insight_generator import InsightGenerator
    generator = InsightGenerator(db)
    result = await generator.generate_all(
        generated_by=str(current_user.id) if current_user else None,
        force=force,
    )
    return result


@router.get("/insights/stats")
async def get_insight_stats(
    db: AsyncSession = Depends(get_db),
):
    """获取 Generated Insights 统计（按原始文档规则）"""
    from agent_os.search_engine.insight_generator import InsightGenerator
    generator = InsightGenerator(db)
    count = await generator.get_generated_insights_count()
    return {"generated_insights": count}


@router.get("/insights/{insight_id}", response_model=InsightClusterResponse)
async def get_insight_cluster(
    insight_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get insight cluster details.

    Args:
        insight_id: Insight UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        Insight cluster details
    """
    try:
        insight_uuid = uuid_pkg.UUID(insight_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid insight_id format")

    stmt = select(InsightCluster).where(InsightCluster.id == insight_uuid)
    result = await db.execute(stmt)
    insight = result.scalar_one_or_none()

    if not insight:
        raise HTTPException(status_code=404, detail="Insight cluster not found")

    return InsightClusterResponse.model_validate(insight)


@router.delete("/insights/{insight_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_insight_cluster(
    insight_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an insight cluster.

    Args:
        insight_id: Insight UUID
        db: Database session
        current_user: Authenticated user

    Returns:
        204 No Content
    """
    try:
        insight_uuid = uuid_pkg.UUID(insight_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid insight_id format")

    stmt = select(InsightCluster).where(InsightCluster.id == insight_uuid)
    result = await db.execute(stmt)
    insight = result.scalar_one_or_none()

    if not insight:
        raise HTTPException(status_code=404, detail="Insight cluster not found")

    await db.delete(insight)
    await db.commit()

