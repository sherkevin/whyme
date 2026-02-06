"""Insight Miner - Stage 5 Implementation.

Discovers insights from high-density connection clusters using LLM.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from agent_os.items.models import Item, GraphEdge
from agent_os.insights.models import (
    InsightExtension,
    InsightCluster,
    generate_claim_hash,
    normalize_claim
)

logger = logging.getLogger(__name__)


# ============================================================================
# LLM Abstraction
# ============================================================================

class LLMClient:
    """
    LLM 客户端抽象 - 用于生成 Insight

    支持 OpenAI、Claude、或本地模型
    """

    def __init__(
        self,
        provider: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        初始化 LLM 客户端

        Args:
            provider: 提供商 ('openai', 'anthropic', 'local')
            api_key: API Key (可选，可从环境变量读取)
            model: 模型名称 (可选)
        """
        self.provider = provider
        self.api_key = api_key
        self.model = model or self._default_model()

    def _default_model(self) -> str:
        """获取默认模型"""
        if self.provider == "openai":
            return "gpt-4o-mini"
        elif self.provider == "anthropic":
            return "claude-3-haiku-20240307"
        else:
            return "gpt-4o-mini"

    async def generate_insight(
        self,
        items: List[Dict[str, Any]],
        connections: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        基于集群生成 Insight

        Args:
            items: 集群中的 Item 列表
            connections: 集群内的连接列表

        Returns:
            Insight 数据: {claim, rationale, implications, confidence}
        """
        # 构建 prompt
        prompt = self._build_prompt(items, connections)

        # 调用 LLM (简化版本 - Stage 5 不实际调用 LLM)
        # 生产环境应该调用真实的 LLM API
        return self._mock_generate_insight(items, connections)

    def _build_prompt(
        self,
        items: List[Dict[str, Any]],
        connections: List[Dict[str, Any]]
    ) -> str:
        """构建 LLM Prompt"""
        # 构建 items 摘要
        items_summary = "\n".join([
            f"- {item['title']}: {item.get('summary', item.get('content', ''))[:200]}"
            for item in items[:5]  # 限制数量
        ])

        # 构建连接摘要
        connections_summary = "\n".join([
            f"- {conn['from_node_id']} <-> {conn['to_node_id']} (score: {conn['weight']:.2f})"
            for conn in connections[:5]
        ])

        prompt = f"""你是一个知识洞察挖掘专家。基于以下相关内容集群，提炼出一个有价值的洞察。

## 内容集群
{items_summary}

## 连接强度
{connections_summary}

请提炼出一个简洁、有洞察力的陈述 (Claim)，并说明推理过程 (Rationale) 和可能的启示 (Implications)。

输出 JSON 格式:
{{
  "claim": "简洁的洞察陈述",
  "rationale": "推理过程",
  "implications": ["启示1", "启示2", "启示3"],
  "confidence": 0.85
}}
"""
        return prompt

    def _mock_generate_insight(
        self,
        items: List[Dict[str, Any]],
        connections: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        模拟生成 Insight (Stage 5 简化版本)

        生产环境应该调用真实的 LLM API
        """
        # 提取关键词作为 claim
        keywords = set()
        for item in items:
            title = item.get('title', '')
            content = item.get('content', '')
            # 简单提取前几个词
            words = (title + ' ' + content).split()[:10]
            keywords.update([w.lower() for w in words if len(w) > 3])

        # 生成模拟 claim
        claim = f"{' '.join(list(keywords)[:5])} 之间存在关联模式"

        # 生成模拟 rationale
        rationale = f"基于 {len(items)} 个相关内容之间的 {len(connections)} 个强连接，发现这些主题在语义上高度相关。"

        # 生成模拟 implications
        implications = [
            "这些主题可以整合为一个更大的知识体系",
            "建议创建相关的行动计划",
            "可以进一步探索这些主题之间的深层联系"
        ]

        return {
            "claim": claim,
            "rationale": rationale,
            "implications": implications,
            "confidence": 0.75
        }


# ============================================================================
# Insight Miner
# ============================================================================

class InsightMiner:
    """
    洞察挖掘引擎

    从高密度连接集群中自动发现 Insight
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        min_cluster_size: int = 3,
        min_connection_weight: float = 0.7
    ):
        """
        初始化挖掘引擎

        Args:
            llm_client: LLM 客户端 (可选)
            min_cluster_size: 最小集群大小
            min_connection_weight: 最小连接权重
        """
        self.llm_client = llm_client or LLMClient()
        self.min_cluster_size = min_cluster_size
        self.min_connection_weight = min_connection_weight

    async def mine_from_cluster(
        self,
        db: AsyncSession,
        cluster_id: uuid.UUID
    ) -> Optional[Dict[str, Any]]:
        """
        从集群挖掘 Insight

        Args:
            db: 数据库会话
            cluster_id: 集群 ID

        Returns:
            挖掘结果
        """
        # 获取集群信息
        cluster_result = await db.execute(
            select(InsightCluster).where(InsightCluster.id == cluster_id)
        )
        cluster = cluster_result.scalar_one_or_none()

        if not cluster:
            logger.error(f"Cluster {cluster_id} not found")
            return None

        # 更新状态为 mining
        cluster.mining_status = "mining"
        await db.commit()

        try:
            # 获取集群中的 items
            item_ids = [uuid.UUID(id_str) for id_str in cluster.item_ids]

            items_result = await db.execute(
                select(Item).where(Item.id.in_(item_ids))
            )
            items = items_result.scalars().all()

            # 获取集群内的连接
            connections_result = await db.execute(
                select(GraphEdge).where(
                    and_(
                        GraphEdge.from_node_id.in_(item_ids),
                        GraphEdge.to_node_id.in_(item_ids),
                        GraphEdge.weight >= self.min_connection_weight
                    )
                )
            )
            connections = connections_result.scalars().all()

            # 准备数据
            items_data = [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "content": item.content,
                    "summary": item.summary,
                    "type": item.type
                }
                for item in items
            ]

            connections_data = [
                {
                    "from_node_id": str(conn.from_node_id),
                    "to_node_id": str(conn.to_node_id),
                    "weight": conn.weight,
                    "relation_type": conn.relation_type
                }
                for conn in connections
            ]

            # 调用 LLM 生成 insight
            try:
                insight_result = await self.llm_client.generate_insight(
                    items_data,
                    connections_data
                )
                if not insight_result:
                    raise ValueError("LLM returned empty result")
            except Exception as e:
                logger.error(f"Error generating insight: {e}")
                cluster.mining_status = "failed"
                cluster.error_message = f"LLM generation error: {e}"
                await db.commit()
                return {
                    "status": "error",
                    "error": str(e)
                }

            # 检查是否重复
            claim_hash = generate_claim_hash(insight_result["claim"])

            existing_result = await db.execute(
                select(InsightExtension).where(
                    InsightExtension.claim_hash == claim_hash
                )
            )
            existing = existing_result.scalar_one_or_none()

            if existing:
                logger.info(f"Insight already exists: {claim_hash}")
                cluster.mining_status = "completed"
                cluster.insight_id = existing.item_id
                await db.commit()
                return {
                    "status": "duplicate",
                    "insight_id": str(existing.item_id),
                    "claim_hash": claim_hash
                }

            # 创建 Insight Item
            from agent_os.items.crud import create_item
            from agent_os.items.schema import ItemCreate

            # 构建 insight 内容
            insight_content = self._format_insight_content(insight_result)

            item_data = ItemCreate(
                workspace_id=cluster.workspace_id,
                creator_id=uuid.uuid4(),  # System user
                type="insight",
                title=insight_result["claim"][:100],
                content=insight_content,
                summary=insight_result["rationale"]
            )

            item = await create_item(db, item_data)

            # 创建 InsightExtension
            insight_extension = InsightExtension(
                item_id=item.id,
                claim=insight_result["claim"],
                rationale=insight_result["rationale"],
                implications=insight_result["implications"],
                claim_hash=claim_hash,
                source_refs=cluster.item_ids,
                confidence_score={
                    "score": insight_result.get("confidence", 0.75),
                    "factors": ["cluster_size", "connection_strength"]
                },
                mining_metadata={
                    "cluster_size": len(items),
                    "connection_count": len(connections),
                    "trigger": "cluster_mining"
                },
                review_status="pending"
            )

            db.add(insight_extension)

            # 更新集群状态
            cluster.mining_status = "completed"
            cluster.insight_id = item.id

            await db.commit()

            logger.info(f"Insight mined successfully: {item.id}")

            return {
                "status": "success",
                "insight_id": str(item.id),
                "claim": insight_result["claim"],
                "claim_hash": claim_hash
            }

        except Exception as e:
            logger.error(f"Error mining insight from cluster {cluster_id}: {e}")
            cluster.mining_status = "failed"
            cluster.error_message = str(e)
            await db.commit()
            return {
                "status": "error",
                "error": str(e)
            }

    def _format_insight_content(self, insight_result: Dict[str, Any]) -> str:
        """格式化 Insight 内容"""
        claim = insight_result.get('claim', '')
        rationale = insight_result.get('rationale', '')
        implications = insight_result.get('implications', [])

        parts = [
            f"## Claim\n{claim}",
        ]

        if rationale:
            parts.append(f"\n## Rationale\n{rationale}")

        parts.append(f"\n## Implications")

        for i, implication in enumerate(implications, 1):
            parts.append(f"{i}. {implication}")

        return "\n".join(parts)

    async def find_high_density_clusters(
        self,
        db: AsyncSession,
        workspace_id: uuid.UUID,
        min_cluster_size: int = 3,
        min_connection_weight: float = 0.7
    ) -> List[List[uuid.UUID]]:
        """
        查找高密度连接集群

        Args:
            db: 数据库会话
            workspace_id: 工作空间 ID
            min_cluster_size: 最小集群大小
            min_connection_weight: 最小连接权重

        Returns:
            集群列表 (每个集群是 item ID 列表)
        """
        # 查询所有强连接
        result = await db.execute(
            select(GraphEdge).where(
                and_(
                    GraphEdge.weight >= min_connection_weight,
                    GraphEdge.is_strong == True
                )
            )
        )
        strong_edges = result.scalars().all()

        # 简化的聚类算法: 基于连接密度
        # 生产环境可以使用更复杂的算法 (如 Louvain, Leiden)

        # 构建邻接表
        adjacency = {}
        for edge in strong_edges:
            from_id = str(edge.from_node_id)
            to_id = str(edge.to_node_id)

            if from_id not in adjacency:
                adjacency[from_id] = set()
            if to_id not in adjacency:
                adjacency[to_id] = set()

            adjacency[from_id].add(to_id)
            adjacency[to_id].add(from_id)

        # 查找连通组件 (简化版)
        clusters = []
        visited = set()

        def dfs(node_id, current_cluster):
            """深度优先搜索查找连通组件"""
            visited.add(node_id)
            current_cluster.append(node_id)

            for neighbor in adjacency.get(node_id, []):
                if neighbor not in visited:
                    dfs(neighbor, current_cluster)

        for node_id in adjacency:
            if node_id not in visited:
                cluster = []
                dfs(node_id, cluster)
                if len(cluster) >= min_cluster_size:
                    clusters.append([uuid.UUID(id_str) for id_str in cluster])

        return clusters

    async def create_cluster(
        self,
        db: AsyncSession,
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
            创建的集群对象
        """
        cluster = InsightCluster(
            workspace_id=workspace_id,
            cluster_type=cluster_type,
            item_ids=[str(item_id) for item_id in item_ids],
            cluster_score={
                "size": len(item_ids)
            },
            mining_status="pending"
        )

        db.add(cluster)
        await db.commit()
        await db.refresh(cluster)

        return cluster


# ============================================================================
# Convenience Functions
# ============================================================================

async def mine_insight_from_items(
    db: AsyncSession,
    item_ids: List[uuid.UUID],
    workspace_id: uuid.UUID,
    llm_client: Optional[LLMClient] = None
) -> Optional[Dict[str, Any]]:
    """
    便捷函数: 从 Item 列表挖掘 Insight

    Args:
        db: 数据库会话
        item_ids: Item ID 列表
        workspace_id: 工作空间 ID
        llm_client: LLM 客户端 (可选)

    Returns:
        挖掘结果
    """
    miner = InsightMiner(llm_client=llm_client)

    # 创建集群
    cluster = await miner.create_cluster(
        db,
        workspace_id,
        item_ids,
        "manual"
    )

    # 挖掘 insight
    return await miner.mine_from_cluster(db, cluster.id)
