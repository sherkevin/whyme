"""Search API Routes - Stage 2 Hybrid Search."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.db.session import get_db
from agent_os.search.hybrid_search import (
    HybridSearchService,
    HybridSearchResult,
    hybrid_search
)
from pydantic import BaseModel, Field


# =============================================================================
# Request/Response Models
# =============================================================================

class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., min_length=1, description="搜索查询")
    type_filters: Optional[List[str]] = Field(
        None,
        description="类型过滤 (note, task, resource, plan, insight)"
    )
    limit: int = Field(20, ge=1, le=100, description="返回数量")


class SearchResponse(BaseModel):
    """搜索响应"""
    results: List[dict]
    total: int
    query: str
    search_time_ms: float


class SearchResultItem(BaseModel):
    """单个搜索结果"""
    item_id: str
    title: str
    snippet: str
    score: float
    match_type: str
    matched_terms: List[str] = []


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/search", tags=["Search - Stage 2"])


@router.post("/hybrid", response_model=SearchResponse)
async def hybrid_search_endpoint(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    混合搜索 API - PRD4 规范

    结合语义搜索和关键词搜索,提供最佳搜索结果

    - **语义搜索**: 使用向量相似度
    - **关键词搜索**: 使用 BM25 算法
    - **融合排序**: 0.7 * semantic + 0.3 * keyword + freshness
    - **高亮显示**: 标记匹配的关键词
    """
    import time

    start_time = time.time()

    try:
        # 执行混合搜索
        results = await hybrid_search(
            db,
            workspace_id="default",  # TODO: 从认证上下文获取
            query=request.query,
            limit=request.limit,
            type_filters=request.type_filters
        )

        # 转换为响应格式
        response_items = []
        for r in results:
            response_items.append({
                "item_id": r.item_id,
                "title": r.title,
                "snippet": r.snippet,
                "score": r.final_score,
                "match_type": r.match_type,
                "matched_terms": r.matched_terms or []
            })

        search_time = (time.time() - start_time) * 1000  # 转换为毫秒

        return SearchResponse(
            results=response_items,
            total=len(response_items),
            query=request.query,
            search_time_ms=round(search_time, 2)
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "hybrid-search"}
