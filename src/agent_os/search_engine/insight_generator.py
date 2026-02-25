"""Insight Generator - Cluster Detection & Insight Generation (G.7)

基于知识图谱的强连接检测认知簇，并生成结构化 Insight。
当前为规则/模板模式，预留 LLM 接口。
"""

import uuid
import hashlib
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from agent_os.items.models import Item, GraphEdge
from agent_os.search_engine.models import InsightCluster

logger = logging.getLogger(__name__)


class InsightGenerator:
    """认知结晶生成器"""

    # 触发条件阈值
    MIN_SOURCE_ITEMS = 2        # 最少来源数量（原始文档要求3，降低到2以适应早期数据少的情况）
    MIN_STRONG_EDGES = 1        # 簇内最少强边数
    STRONG_THRESHOLD = 0.50     # 强边阈值（与 ConnectionEngine 的 THRESHOLD_MEDIUM 对齐）

    def __init__(self, db: AsyncSession):
        self.db = db

    # ========== 1. Cluster 检测 ==========

    async def detect_clusters(self) -> List[Dict]:
        """
        从知识图谱的强边中检测连通子图（认知簇）

        Returns:
            List of clusters, each: {
                'cluster_id': str,
                'node_ids': List[uuid.UUID],
                'edges': List[GraphEdge],
                'strength': float  # 平均边权重
            }
        """
        # 获取所有强边（weight >= threshold）
        result = await self.db.execute(
            select(GraphEdge).where(GraphEdge.weight >= self.STRONG_THRESHOLD)
        )
        strong_edges = result.scalars().all()

        if not strong_edges:
            return []

        # 构建邻接表
        adjacency: Dict[uuid.UUID, set] = defaultdict(set)
        edge_map: Dict[Tuple, GraphEdge] = {}

        for edge in strong_edges:
            adjacency[edge.from_node_id].add(edge.to_node_id)
            adjacency[edge.to_node_id].add(edge.from_node_id)
            edge_map[(edge.from_node_id, edge.to_node_id)] = edge

        # BFS 找连通分量
        visited = set()
        clusters = []

        for start_node in adjacency:
            if start_node in visited:
                continue

            # BFS
            component_nodes = set()
            queue = [start_node]
            while queue:
                node = queue.pop(0)
                if node in visited:
                    continue
                visited.add(node)
                component_nodes.add(node)
                for neighbor in adjacency[node]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            # 收集该连通分量的边
            component_edges = []
            for edge in strong_edges:
                if edge.from_node_id in component_nodes and edge.to_node_id in component_nodes:
                    component_edges.append(edge)

            # 过滤：至少 MIN_SOURCE_ITEMS 个节点
            if len(component_nodes) >= self.MIN_SOURCE_ITEMS and len(component_edges) >= self.MIN_STRONG_EDGES:
                avg_weight = sum(e.weight for e in component_edges) / len(component_edges)
                cluster_id = hashlib.md5(
                    '|'.join(sorted(str(n) for n in component_nodes)).encode()
                ).hexdigest()[:16]

                clusters.append({
                    'cluster_id': cluster_id,
                    'node_ids': list(component_nodes),
                    'edges': component_edges,
                    'strength': round(avg_weight, 4),
                })

        # 按强度排序
        clusters.sort(key=lambda c: c['strength'], reverse=True)
        return clusters

    # ========== 2. 触发条件判断 ==========

    def should_generate(self, cluster: Dict) -> bool:
        """判断一个 cluster 是否满足 Insight 生成条件"""
        if len(cluster['node_ids']) < self.MIN_SOURCE_ITEMS:
            return False
        if len(cluster['edges']) < self.MIN_STRONG_EDGES:
            return False
        return True

    # ========== 3. 检查去重 ==========

    async def check_duplicate(self, cluster_id: str) -> Optional[InsightCluster]:
        """检查该 cluster 是否已生成过 Insight"""
        result = await self.db.execute(
            select(InsightCluster).where(
                and_(
                    InsightCluster.cluster_id == cluster_id,
                    InsightCluster.cluster_type == 'insight',
                    InsightCluster.status != 'deprecated',
                )
            )
        )
        return result.scalar_one_or_none()

    # ========== 4. 生成 Insight（规则/模板模式） ==========

    async def generate_insight_for_cluster(
        self,
        cluster: Dict,
        generated_by: str = None,
    ) -> Optional[InsightCluster]:
        """
        为一个 cluster 生成 Insight

        当前实现：基于节点内容的规则/模板生成
        未来：替换为 LLM 调用
        """
        # 检查去重
        existing = await self.check_duplicate(cluster['cluster_id'])
        if existing:
            # 更新 evidence_count
            existing.evidence_count = (existing.evidence_count or 1) + 1
            existing.stability_score = min(1.0, (existing.stability_score or 0.5) + 0.05)
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        # 获取节点内容
        items = []
        for nid in cluster['node_ids']:
            result = await self.db.execute(select(Item).where(Item.id == nid))
            item = result.scalar_one_or_none()
            if item:
                items.append(item)

        if len(items) < self.MIN_SOURCE_ITEMS:
            return None

        # ---- 规则/模板生成 ----
        # 提取所有标题和内容片段
        titles = [item.title or '' for item in items if item.title]
        contents = [item.content[:200] if item.content else '' for item in items]

        # 找共同关键词作为主题
        from agent_os.connections.extractors import KeywordExtractor
        extractor = KeywordExtractor()
        all_keywords = []
        for item in items:
            text = f"{item.title or ''} {item.content or ''}"
            kws = extractor.extract(text, top_k=10)
            all_keywords.extend(kws)

        # 统计词频找核心主题
        kw_counts = defaultdict(int)
        for kw in all_keywords:
            kw_counts[kw] += 1
        common_keywords = sorted(kw_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        theme_words = [kw for kw, _ in common_keywords] if common_keywords else ['未知主题']

        # 生成 claim（模板模式）
        theme_str = '、'.join(theme_words[:3])
        claim = f"围绕「{theme_str}」的 {len(items)} 条内容之间存在结构性关联，形成了一个认知簇。"

        # 生成 rationale
        edge_descriptions = []
        for edge in cluster['edges'][:3]:
            from_item = next((i for i in items if i.id == edge.from_node_id), None)
            to_item = next((i for i in items if i.id == edge.to_node_id), None)
            if from_item and to_item:
                edge_descriptions.append(
                    f"「{from_item.title or '无标题'}」与「{to_item.title or '无标题'}」"
                    f"（关联度 {edge.weight:.0%}）"
                )
        rationale = '；'.join(edge_descriptions) if edge_descriptions else '多条内容之间存在语义和关键词重叠。'

        # 生成 implications
        implications = f"建议深入整理「{theme_str}」相关内容，可能形成更系统的认知框架。"

        # 计算 canonical_hash
        normalized_claim = claim.strip().lower()
        canonical_hash = hashlib.sha256(normalized_claim.encode()).hexdigest()[:32]

        # 判断 level（基于簇大小和强度）
        if cluster['strength'] >= 0.8 and len(items) >= 5:
            level = 3  # strategic
        elif cluster['strength'] >= 0.6 and len(items) >= 3:
            level = 2  # structural
        else:
            level = 1  # tactical

        # 判断 insight_type
        insight_type = 'pattern'  # 模板模式默认为 pattern

        # 质量分数（模板模式固定给 0.6，LLM 模式可以更高）
        quality_score = 0.6

        # 创建 InsightCluster
        insight = InsightCluster(
            cluster_type='insight',
            name=f"认知簇：{theme_str}",
            description=claim,
            source_item_type='mixed',
            source_item_ids=[str(nid) for nid in cluster['node_ids']],
            insight_data={
                'titles': titles,
                'theme_keywords': theme_words,
                'cluster_strength': cluster['strength'],
                'edge_count': len(cluster['edges']),
                'node_count': len(items),
                'generation_mode': 'template',  # 标记为模板模式
            },
            confidence=cluster['strength'],
            sample_count=len(items),
            parameters={'cluster_id': cluster['cluster_id']},
            generated_by=generated_by,
            # G.7 扩展字段
            claim=claim,
            rationale=rationale,
            implications=implications,
            insight_type=insight_type,
            quality_score=quality_score,
            stability_score=cluster['strength'],
            level=level,
            status='emerging' if level < 2 else 'stable',
            canonical_hash=canonical_hash,
            evidence_count=1,
            cluster_id=cluster['cluster_id'],
            theme_id=theme_words[0] if theme_words else None,
            is_valid_insight=level >= 2,
        )

        self.db.add(insight)
        await self.db.commit()
        await self.db.refresh(insight)
        return insight

    # ========== 5. 批量生成 ==========

    async def generate_all(self, generated_by: str = None, force: bool = False) -> Dict:
        """
        检测所有 cluster 并生成 Insight

        Args:
            generated_by: 触发用户 ID
            force: 是否强制重新生成（清除旧的 insight 类型记录）

        Returns:
            生成结果统计
        """
        if force:
            from sqlalchemy import delete as sql_delete
            await self.db.execute(
                sql_delete(InsightCluster).where(InsightCluster.cluster_type == 'insight')
            )
            await self.db.commit()

        clusters = await self.detect_clusters()
        generated = 0
        updated = 0
        skipped = 0

        for cluster in clusters:
            if not self.should_generate(cluster):
                skipped += 1
                continue

            existing = await self.check_duplicate(cluster['cluster_id'])
            insight = await self.generate_insight_for_cluster(cluster, generated_by)

            if insight:
                if existing:
                    updated += 1
                else:
                    generated += 1
            else:
                skipped += 1

        return {
            'clusters_detected': len(clusters),
            'insights_generated': generated,
            'insights_updated': updated,
            'insights_skipped': skipped,
        }

    # ========== 6. 统计 ==========

    async def get_generated_insights_count(self) -> int:
        """
        获取 Generated Insights 计数
        规则：status=stable AND level>=2 AND status!=deprecated
        """
        result = await self.db.execute(
            select(func.count(InsightCluster.id)).where(
                and_(
                    InsightCluster.cluster_type == 'insight',
                    InsightCluster.status == 'stable',
                    InsightCluster.level >= 2,
                    InsightCluster.is_valid_insight == True,
                )
            )
        )
        return result.scalar_one_or_none() or 0
