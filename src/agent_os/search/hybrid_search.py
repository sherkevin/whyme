"""Hybrid Search Service - Stage 2 Implementation.

Combines semantic (vector) and keyword (BM25) search with RRF fusion.
"""

import asyncio
import logging
import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.search.keyword_search import KeywordSearchService, KeywordSearchResult

logger = logging.getLogger(__name__)


class HybridSearchResult:
    """混合搜索结果"""

    def __init__(
        self,
        item_id: str,
        title: str,
        snippet: str,
        semantic_score: float,
        keyword_score: float,
        final_score: float,
        match_type: str,  # "semantic", "keyword", "hybrid"
        matched_terms: List[str] = None
    ):
        self.item_id = item_id
        self.title = title
        self.snippet = snippet
        self.semantic_score = semantic_score
        self.keyword_score = keyword_score
        self.final_score = final_score
        self.match_type = match_type
        self.matched_terms = matched_terms or []


class HybridSearchService:
    """混合搜索服务 - PRD4 规范实现"""

    def __init__(
        self,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        freshness_days: int = 30
    ):
        """
        初始化混合搜索服务

        Args:
            semantic_weight: 语义搜索权重 (PRD4: 0.7)
            keyword_weight: 关键词搜索权重 (PRD4: 0.3)
            freshness_days: 新鲜度计算天数
        """
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.freshness_days = freshness_days

        self.keyword_service = KeywordSearchService()
        # embedding_service will be initialized in Stage 3 when vector search is implemented

    async def search(
        self,
        db: AsyncSession,
        *,
        workspace_id: str,
        query: str,
        limit: int = 20,
        type_filters: Optional[List[str]] = None
    ) -> List[HybridSearchResult]:
        """
        执行混合搜索 - PRD4 规范流程

        Args:
            db: 数据库会话
            workspace_id: 工作空间ID
            query: 搜索查询
            limit: 返回结果数量
            type_filters: 类型过滤

        Returns:
            混合搜索结果列表
        """
        # 1. 空 query 检查 -> 按 updated_at 倒序返回
        if not query or not query.strip():
            logger.info("Empty query, returning recent items")
            return await self._get_recent_items(db, workspace_id, limit)

        # 2. 并行召回
        logger.info(f"Executing parallel recall for query: {query}")
        keyword_results, semantic_results = await asyncio.gather(
            self._keyword_search(db, workspace_id, query, limit, type_filters),
            self._semantic_search(db, workspace_id, query, limit, type_filters)
        )

        # 3. 融合排序
        merged_results = self._merge_and_rank(
            keyword_results,
            semantic_results,
            query
        )

        # 4. 高亮处理
        for result in merged_results:
            result.snippet = self._apply_highlight(result.snippet, keyword_results)

        return merged_results[:limit]

    async def _get_recent_items(
        self,
        db: AsyncSession,
        workspace_id: str,
        limit: int
    ) -> List[HybridSearchResult]:
        """空查询处理 - 返回最近更新的Items"""
        from agent_os.items.models import Item
        from sqlalchemy import select, desc

        # Convert workspace_id string to UUID for SQLAlchemy
        try:
            workspace_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
        except (ValueError, AttributeError):
            logger.error(f"Invalid workspace_id: {workspace_id}")
            return []

        result = await db.execute(
            select(Item)
            .where(
                and_(
                    Item.workspace_id == workspace_uuid,
                    Item.status == "active"
                )
            )
            .order_by(desc(Item.updated_at))
            .limit(limit)
        )
        items = result.scalars().all()

        return [
            HybridSearchResult(
                item_id=str(item.id),
                title=item.title or "",
                snippet=(item.content or "")[:200] + "..." if len(item.content or "") > 200 else (item.content or ""),
                semantic_score=0.0,
                keyword_score=0.0,
                final_score=0.0,
                match_type="recent"
            )
            for item in items
        ]

    async def _keyword_search(
        self,
        db: AsyncSession,
        workspace_id: str,
        query: str,
        limit: int,
        type_filters: Optional[List[str]]
    ) -> List[KeywordSearchResult]:
        """路 B: 关键词搜索 (BM25)"""
        logger.info(f"Executing keyword search for: {query}")
        return await self.keyword_service.search(
            db,
            workspace_id=workspace_id,
            query=query,
            limit=limit,
            type_filters=type_filters
        )

    async def _semantic_search(
        self,
        db: AsyncSession,
        workspace_id: str,
        query: str,
        limit: int,
        type_filters: Optional[List[str]]
    ) -> Dict[str, float]:
        """路 A: 语义搜索 (Vector Similarity)"""
        logger.info(f"Executing semantic search for: {query}")

        # TODO Stage 3: 实现 pgvector 向量搜索
        # 注意: 这里简化处理,实际应该使用 pgvector
        # 由于 SQLite 不支持向量搜索,返回空结果
        # 在生产环境中,这应该:
        # 1. 生成查询向量 (需要 EmbeddingService)
        # 2. 使用 pgvector 的 <-> 操作符计算余弦相似度
        # 3. 返回 Top K 结果及其相似度分数
        #
        # 示例 SQL:
        # SELECT id, title, 1 - (embedding <=> query_embedding) as similarity
        # FROM items
        # WHERE workspace_id = :workspace_id
        #   AND embedding IS NOT NULL
        # ORDER BY embedding <=> query_embedding
        # LIMIT :limit

        # 目前返回空,依赖关键词搜索
        return {}

    def _merge_and_rank(
        self,
        keyword_results: List[KeywordSearchResult],
        semantic_results: Dict[str, float],
        query: str
    ) -> List[HybridSearchResult]:
        """
        融合排序 - PRD4 规范

        Final Score = 0.7 * Semantic + 0.3 * Keyword + Freshness

        Args:
            keyword_results: 关键词搜索结果
            semantic_results: 语义搜索结果 (item_id -> score)
            query: 原始查询

        Returns:
            融合后的结果列表
        """
        # 创建 item_id -> KeywordSearchResult 映射
        keyword_map = {r.item_id: r for r in keyword_results}

        # 计算融合分数
        merged = {}

        # 处理关键词结果
        for kw_result in keyword_results:
            item_id = kw_result.item_id
            keyword_score = kw_result.score / 10.0  # 归一化到 [0, 1]
            if keyword_score > 1:
                keyword_score = 1.0

            merged[item_id] = HybridSearchResult(
                item_id=item_id,
                title=kw_result.title,
                snippet=kw_result.content_snippet,
                semantic_score=0.0,
                keyword_score=keyword_score,
                final_score=keyword_score * self.keyword_weight,
                match_type="keyword",
                matched_terms=kw_result.matched_terms
            )

        # 如果有语义搜索结果,融合进来
        if semantic_results:
            max_semantic_score = max(semantic_results.values()) if semantic_results else 1.0

            for item_id, semantic_score in semantic_results.items():
                semantic_score_normalized = semantic_score / max_semantic_score

                if item_id in merged:
                    # 已有关键词结果,融合
                    existing = merged[item_id]
                    existing.semantic_score = semantic_score_normalized
                    existing.final_score = (
                        self.semantic_weight * semantic_score_normalized +
                        self.keyword_weight * existing.keyword_score
                    )
                    existing.match_type = "hybrid"
                else:
                    # 只有语义结果
                    merged[item_id] = HybridSearchResult(
                        item_id=item_id,
                        title="",  # 需要从数据库获取
                        snippet="",
                        semantic_score=semantic_score_normalized,
                        keyword_score=0.0,
                        final_score=semantic_score_normalized * self.semantic_weight,
                        match_type="semantic"
                    )

        # 添加新鲜度加权
        for item_id, result in merged.items():
            fresh_boost = self._calculate_freshness_boost(item_id)
            result.final_score *= (1.0 + 0.1 * fresh_boost)

        # 按最终分数排序
        sorted_results = sorted(
            merged.values(),
            key=lambda x: x.final_score,
            reverse=True
        )

        return sorted_results

    def _calculate_freshness_boost(self, item_id: str) -> float:
        """
        计算新鲜度加权

        Args:
            item_id: Item ID

        Returns:
            新鲜度加权值
        """
        # 简化实现: 基于 item_id 的哈希值模拟时间
        # 实际应该查询 updated_at 字段

        # 这里简化处理,返回一个基于 ID 的伪随机值
        # 在生产环境中应该查询实际的 updated_at
        hash_val = hash(item_id) % 100
        return max(0, (100 - hash_val) / 100.0)

    def _apply_highlight(
        self,
        snippet: str,
        keyword_results: List[KeywordSearchResult]
    ) -> str:
        """
        应用高亮处理

        Args:
            snippet: 内容片段
            keyword_results: 关键词搜索结果

        Returns:
            高亮后的内容
        """
        # 收集所有匹配的词
        all_terms = set()
        for result in keyword_results:
            all_terms.update(result.matched_terms)

        if not all_terms:
            return snippet

        # 简单的高亮实现: 用 ** 标记匹配词
        highlighted = snippet
        for term in all_terms:
            import re
            # 不区分大小写替换
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            highlighted = pattern.sub(f"**{term}**", highlighted)

        return highlighted


# =============================================================================
# 便捷函数
# =============================================================================

async def hybrid_search(
    db: AsyncSession,
    *,
    workspace_id: str,
    query: str,
    limit: int = 20,
    type_filters: Optional[List[str]] = None
) -> List[HybridSearchResult]:
    """
    混合搜索 - 统一接口

    Args:
        db: 数据库会话
        workspace_id: 工作空间ID
        query: 搜索查询
        limit: 返回数量
        type_filters: 类型过滤

    Returns:
        搜索结果列表
    """
    service = HybridSearchService()
    return await service.search(
        db,
        workspace_id=workspace_id,
        query=query,
        limit=limit,
        type_filters=type_filters
    )
