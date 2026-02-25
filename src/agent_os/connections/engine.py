"""Connection Calculation Engine - Stage 3 Implementation.

Computes 5-dimensional connection scores between Items for Cognitive Graph.
"""

import logging
from typing import List, Tuple, Dict, Optional
from datetime import datetime, timedelta
import uuid

from agent_os.items.models import Item

logger = logging.getLogger(__name__)


class ConnectionEngine:
    """
    连接计算引擎 - 5维度连接评分

    计算2个Item之间的连接强度，基于5个维度:
    1. Vector Similarity (40%) - 向量相似度 (余弦相似度)
    2. Keyword Overlap (20%) - 关键词重叠度 (Jaccard系数)
    3. Entity Overlap (20%) - 实体重叠度 (NER)
    4. Same Area (10%) - 同区域加权
    5. Time Decay (10%) - 时间衰减 (指数衰减)
    """

    # 权重配置
    WEIGHT_VECTOR = 0.40
    WEIGHT_KEYWORD = 0.20
    WEIGHT_ENTITY = 0.20
    WEIGHT_AREA = 0.10
    WEIGHT_TIME = 0.10

    # 阈值配置
    THRESHOLD_STRONG = 0.75  # 强连接阈值
    THRESHOLD_MEDIUM = 0.50  # 中等连接阈值

    # 时间衰减配置
    TIME_DECAY_HALFLIFE = 30  # 半衰期30天

    def __init__(
        self,
        vector_weight: float = WEIGHT_VECTOR,
        keyword_weight: float = WEIGHT_KEYWORD,
        entity_weight: float = WEIGHT_ENTITY,
        area_weight: float = WEIGHT_AREA,
        time_weight: float = WEIGHT_TIME
    ):
        """
        初始化连接引擎

        Args:
            vector_weight: 向量相似度权重
            keyword_weight: 关键词重叠权重
            entity_weight: 实体重叠权重
            area_weight: 区域权重
            time_weight: 时间权重
        """
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.entity_weight = entity_weight
        self.area_weight = area_weight
        self.time_weight = time_weight

        # 延迟导入提取器 (避免循环依赖)
        self._keyword_extractor = None
        self._entity_extractor = None

    async def calculate_score(
        self,
        item_a: Item,
        item_b: Item
    ) -> float:
        """
        计算两个Item之间的连接分数

        Args:
            item_a: Item A
            item_b: Item B

        Returns:
            连接分数 (0.0 - 1.0)
        """
        try:
            # 1. Vector Similarity (40%)
            vector_sim = await self._calculate_vector_similarity(item_a, item_b)

            # 2. Keyword Overlap (20%)
            keyword_overlap = await self._calculate_keyword_overlap(item_a, item_b)

            # 3. Entity Overlap (20%)
            entity_overlap = await self._calculate_entity_overlap(item_a, item_b)

            # 4. Same Area (10%)
            area_score = self._calculate_area_score(item_a, item_b)

            # 5. Time Decay (10%)
            time_score = self._calculate_time_decay(item_a, item_b)

            # 加权求和
            total_score = (
                self.vector_weight * vector_sim +
                self.keyword_weight * keyword_overlap +
                self.entity_weight * entity_overlap +
                self.area_weight * area_score +
                self.time_weight * time_score
            )

            logger.debug(
                f"Connection score: {total_score:.3f} "
                f"(vector={vector_sim:.2f}, keywords={keyword_overlap:.2f}, "
                f"entities={entity_overlap:.2f}, area={area_score:.2f}, time={time_score:.2f})"
            )

            return round(total_score, 4)

        except Exception as e:
            logger.error(f"Error calculating connection score: {e}")
            return 0.0

    async def _calculate_vector_similarity(
        self,
        item_a: Item,
        item_b: Item
    ) -> float:
        """
        计算向量相似度 (余弦相似度)

        Args:
            item_a: Item A
            item_b: Item B

        Returns:
            相似度 (0.0 - 1.0)
        """
        # Stage 3 简化实现: 如果有embedding则计算，否则返回0
        try:
            emb_a = item_a.embedding
            emb_b = item_b.embedding

            # 如果没有embedding或为None，返回0
            if not emb_a or not emb_b:
                return 0.0

            # 处理JSON格式 (SQLite fallback)
            if isinstance(emb_a, dict):
                emb_a = emb_a.get("vector", [])
            if isinstance(emb_b, dict):
                emb_b = emb_b.get("vector", [])

            # 转换为list
            if not isinstance(emb_a, (list, tuple)):
                return 0.0
            if not isinstance(emb_b, (list, tuple)):
                return 0.0

            # 确保长度一致
            if len(emb_a) != len(emb_b):
                return 0.0

            # 计算余弦相似度
            return self._cosine_similarity(emb_a, emb_b)

        except Exception as e:
            logger.warning(f"Error calculating vector similarity: {e}")
            return 0.0

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """
        计算余弦相似度

        cos(θ) = (A · B) / (||A|| * ||B||)

        Args:
            vec_a: 向量A
            vec_b: 向量B

        Returns:
            余弦相似度 (0.0 - 1.0)
        """
        try:
            # 点积
            dot_product = sum(a * b for a, b in zip(vec_a, vec_b))

            # 模
            norm_a = sum(a * a for a in vec_a) ** 0.5
            norm_b = sum(b * b for b in vec_b) ** 0.5

            # 避免除零
            if norm_a == 0 or norm_b == 0:
                return 0.0

            similarity = dot_product / (norm_a * norm_b)

            # 确保在 [0, 1] 范围内
            return max(0.0, min(1.0, similarity))

        except Exception as e:
            logger.warning(f"Error in cosine similarity: {e}")
            return 0.0

    async def _calculate_keyword_overlap(
        self,
        item_a: Item,
        item_b: Item
    ) -> float:
        """
        计算关键词重叠度 (Jaccard系数)

        J(A,B) = |A ∩ B| / |A ∪ B|

        Args:
            item_a: Item A
            item_b: Item B

        Returns:
            重叠度 (0.0 - 1.0)
        """
        try:
            # 提取关键词
            keywords_a = await self._extract_keywords(item_a)
            keywords_b = await self._extract_keywords(item_b)

            if not keywords_a or not keywords_b:
                return 0.0

            # 计算Jaccard系数
            set_a = set(keywords_a)
            set_b = set(keywords_b)

            intersection = len(set_a & set_b)
            union = len(set_a | set_b)

            if union == 0:
                return 0.0
            
            # 如果 Jaccard 为 0，尝试字符级重叠（中文兜底）
            if intersection == 0:
                text_a = f"{item_a.title or ''} {item_a.content or ''}"
                text_b = f"{item_b.title or ''} {item_b.content or ''}"
                chars_a = set(text_a)
                chars_b = set(text_b)
                char_intersection = len(chars_a & chars_b)
                char_union = len(chars_a | chars_b)
                if char_union > 0:
                    return char_intersection / char_union
                return 0.0

            return intersection / union

        except Exception as e:
            logger.warning(f"Error calculating keyword overlap: {e}")
            return 0.0

    async def _calculate_entity_overlap(
        self,
        item_a: Item,
        item_b: Item
    ) -> float:
        """
        计算实体重叠度 (人名、地名、组织名)

        Args:
            item_a: Item A
            item_b: Item B

        Returns:
            重叠度 (0.0 - 1.0)
        """
        try:
            # 提取实体
            entities_a = await self._extract_entities(item_a)
            entities_b = await self._extract_entities(item_b)

            if not entities_a or not entities_b:
                return 0.0

            # 计算Jaccard系数
            set_a = set(entities_a)
            set_b = set(entities_b)

            intersection = len(set_a & set_b)
            union = len(set_a | set_b)

            if union == 0:
                return 0.0

            return intersection / union

        except Exception as e:
            logger.warning(f"Error calculating entity overlap: {e}")
            return 0.0

    def _calculate_area_score(
        self,
        item_a: Item,
        item_b: Item
    ) -> float:
        """
        计算同区域分数

        如果两个Item在同一个Area，返回1.0，否则返回0.0

        Args:
            item_a: Item A
            item_b: Item B

        Returns:
            分数 (0.0 或 1.0)
        """
        try:
            # 检查area_id
            if not item_a.area_id or not item_b.area_id:
                return 0.0

            # 比较area_id
            if item_a.area_id == item_b.area_id:
                return 1.0

            return 0.0

        except Exception as e:
            logger.warning(f"Error calculating area score: {e}")
            return 0.0

    def _calculate_time_decay(
        self,
        item_a: Item,
        item_b: Item
    ) -> float:
        """
        计算时间衰减分数

        使用指数衰减: exp(-|days| / half_life)
        30天时: exp(-30/30) = exp(-1) ≈ 0.368
        1天时: exp(-1/30) ≈ 0.967

        Args:
            item_a: Item A
            item_b: Item B

        Returns:
            衰减分数 (0.0 - 1.0)
        """
        try:
            import math

            # 获取updated_at
            time_a = item_a.updated_at
            time_b = item_b.updated_at

            if not time_a or not time_b:
                return 0.0

            # 计算时间差 (天数)
            time_diff = abs((time_a - time_b).days)

            # 指数衰减: exp(-days / halflife)
            decay = math.exp(-time_diff / self.TIME_DECAY_HALFLIFE)

            return decay

        except Exception as e:
            logger.warning(f"Error calculating time decay: {e}")
            return 0.0

    async def _extract_keywords(self, item: Item) -> List[str]:
        """
        提取Item的关键词

        Args:
            item: Item对象

        Returns:
            关键词列表
        """
        try:
            # 延迟导入提取器
            if self._keyword_extractor is None:
                from agent_os.connections.extractors import KeywordExtractor
                self._keyword_extractor = KeywordExtractor()

            # 合并title和content
            text = f"{item.title or ''} {item.content or ''}"

            # 提取关键词
            keywords = self._keyword_extractor.extract(text, top_k=10)

            return keywords

        except Exception as e:
            logger.warning(f"Error extracting keywords from item {item.id}: {e}")
            return []

    async def _extract_entities(self, item: Item) -> List[str]:
        """
        提取Item的实体 (人名、地名、组织名)

        Args:
            item: Item对象

        Returns:
            实体列表
        """
        try:
            # 延迟导入提取器
            if self._entity_extractor is None:
                from agent_os.connections.extractors import EntityExtractor
                self._entity_extractor = EntityExtractor()

            # 合并title和content
            text = f"{item.title or ''} {item.content or ''}"

            # 提取实体
            entities = self._entity_extractor.extract(text)

            return entities

        except Exception as e:
            logger.warning(f"Error extracting entities from item {item.id}: {e}")
            return []

    def is_strong_connection(self, score: float) -> bool:
        """
        判断是否为强连接

        Args:
            score: 连接分数

        Returns:
            是否为强连接
        """
        return score >= self.THRESHOLD_STRONG

    def get_relation_type(self, score: float) -> str:
        """
        根据分数判断关系类型

        Args:
            score: 连接分数

        Returns:
            关系类型 ('topic', 'causal', 'supplement')
        """
        if score >= self.THRESHOLD_STRONG:
            return "topic"  # 强主题相关
        elif score >= self.THRESHOLD_MEDIUM:
            return "causal"  # 因果关系
        else:
            return "supplement"  # 补充关系


# =============================================================================
# 便捷函数
# =============================================================================

async def calculate_connection(
    item_a: Item,
    item_b: Item,
    engine: Optional[ConnectionEngine] = None
) -> float:
    """
    计算两个Item之间的连接分数

    Args:
        item_a: Item A
        item_b: Item B
        engine: 连接引擎 (可选)

    Returns:
        连接分数 (0.0 - 1.0)
    """
    if engine is None:
        engine = ConnectionEngine()

    return await engine.calculate_score(item_a, item_b)
