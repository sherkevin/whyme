"""Keyword Search Service - BM25 Implementation for Stage 2."""

import logging
import uuid
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, cast

from agent_os.items.models import Item

logger = logging.getLogger(__name__)


class KeywordSearchResult:
    """关键词搜索结果"""

    def __init__(
        self,
        item_id: str,
        title: str,
        content_snippet: str,
        score: float,
        matched_terms: List[str]
    ):
        self.item_id = item_id
        self.title = title
        self.content_snippet = content_snippet
        self.score = score
        self.matched_terms = matched_terms


class KeywordSearchService:
    """关键词搜索服务 - BM25算法实现"""

    def __init__(self):
        # BM25 参数
        self.k1 = 1.2  # 词频饱和参数
        self.b = 0.75  # 长度归一化参数

    async def search(
        self,
        db: AsyncSession,
        *,
        workspace_id: str,
        query: str,
        limit: int = 50,
        type_filters: Optional[List[str]] = None
    ) -> List[KeywordSearchResult]:
        """
        执行关键词搜索

        Args:
            db: 数据库会话
            workspace_id: 工作空间ID
            query: 搜索查询
            limit: 返回结果数量
            type_filters: 类型过滤

        Returns:
            搜索结果列表
        """
        if not query or not query.strip():
            return []

        # 分词和预处理
        terms = self._tokenize_query(query)
        if not terms:
            return []

        # Convert workspace_id string to UUID for SQLAlchemy
        try:
            workspace_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
        except (ValueError, AttributeError):
            logger.error(f"Invalid workspace_id: {workspace_id}")
            return []

        # 构建查询条件
        conditions = [
            Item.workspace_id == workspace_uuid,
            Item.status == "active"
        ]

        if type_filters:
            conditions.append(Item.type.in_(type_filters))

        # 使用 LIKE 搜索 (SQLite兼容,后续可升级到 tsvector)
        # 计算每个文档的相关性评分
        query_conditions = []
        for term in terms:
            query_conditions.append(
                or_(
                    Item.title.ilike(f"%{term}%"),
                    Item.content.ilike(f"%{term}%")
                )
            )

        if query_conditions:
            conditions.append(and_(*query_conditions))

        # 执行查询
        result = await db.execute(
            select(Item)
            .where(and_(*conditions))
            .order_by(Item.updated_at.desc())
        )
        items = result.scalars().all()

        # 计算 BM25 分数并排序
        scored_results = []
        for item in items:
            score, matched_terms = self._calculate_bm25_score(
                item,
                terms
            )
            if score > 0:
                # 生成内容片段 (带高亮)
                snippet = self._generate_snippet(
                    item.content or "",
                    terms,
                    max_length=200
                )
                scored_results.append(
                    KeywordSearchResult(
                        item_id=str(item.id),
                        title=item.title or "",
                        content_snippet=snippet,
                        score=score,
                        matched_terms=matched_terms
                    )
                )

        # 按分数排序并返回 Top N
        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:limit]

    def _tokenize_query(self, query: str) -> List[str]:
        """
        分词 - 简化版本 (实际应使用专业的中文分词)

        Args:
            query: 查询字符串

        Returns:
            词列表
        """
        # 简化分词: 按空格分割,转小写,去重
        terms = query.lower().split()
        # 过滤停用词
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'from', 'as', 'is', 'it', 'that',
            '这', '的', '了', '和', '是', '在', '有', '我', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这'
        }
        terms = [t for t in terms if len(t) > 1 and t not in stopwords]
        return list(set(terms))  # 去重

    def _calculate_bm25_score(
        self,
        item: Item,
        terms: List[str]
    ) -> Tuple[float, List[str]]:
        """
        计算 BM25 分数

        Args:
            item: Item 对象
            terms: 查询词列表

        Returns:
            (分数, 匹配的词列表)
        """
        matched_terms = []
        title = (item.title or "").lower()
        content = (item.content or "").lower()

        # 简化的 BM25 实现
        # 实际应该包含:
        # - IDF 计算
        # - 词频统计
        # - 文档长度归一化

        score = 0.0
        for term in terms:
            term_count = 0

            # 在标题中匹配 (权重 2x)
            if term in title:
                term_count += title.count(term) * 2

            # 在内容中匹配
            if term in content:
                term_count += content.count(term)

            if term_count > 0:
                matched_terms.append(term)
                # 简化的分数计算
                score += term_count

        # 根据文档长度进行轻微惩罚 (越长的文档权重越低)
        doc_length = len(title) + len(content)
        length_penalty = 1.0 / (1.0 + doc_length / 10000.0)
        score *= length_penalty

        # 新鲜度加权 (最近更新的文档加分)
        # 这里简化处理,实际应该使用 updated_at

        return score, matched_terms

    def _generate_snippet(
        self,
        content: str,
        terms: List[str],
        max_length: int = 200
    ) -> str:
        """
        生成带高亮的内容片段

        Args:
            content: 原始内容
            terms: 匹配的词
            max_length: 最大长度

        Returns:
            高亮片段
        """
        if not content:
            return ""

        content_lower = content.lower()

        # 找到第一个匹配位置
        first_match_pos = -1
        for term in terms:
            pos = content_lower.find(term)
            if pos != -1:
                if first_match_pos == -1 or pos < first_match_pos:
                    first_match_pos = pos

        # 如果没有匹配,返回开头
        if first_match_pos == -1:
            return content[:max_length]

        # 提取上下文 (匹配位置前后各取一些内容)
        context_size = (max_length - len(terms[0])) // 2
        start = max(0, first_match_pos - context_size)
        end = min(len(content), first_match_pos + max_length)

        snippet = content[start:end]

        # 添加省略号
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet


# =============================================================================
# 便捷函数
# =============================================================================

async def search_by_keywords(
    db: AsyncSession,
    *,
    workspace_id: str,
    query: str,
    limit: int = 50,
    type_filters: Optional[List[str]] = None
) -> List[KeywordSearchResult]:
    """
    按关键词搜索 Items

    Args:
        db: 数据库会话
        workspace_id: 工作空间ID
        query: 搜索查询
        limit: 返回结果数量
        type_filters: 类型过滤

    Returns:
        搜索结果列表
    """
    service = KeywordSearchService()
    return await service.search(
        db,
        workspace_id=workspace_id,
        query=query,
        limit=limit,
        type_filters=type_filters
    )
