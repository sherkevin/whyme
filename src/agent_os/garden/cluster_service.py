"""Cluster Strength Calculation and Insight Worker - PRD8 Module 2.

Provides:
- Cluster strength calculation using the formula
- Insight aggregation worker for status transitions and deduplication
"""

import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.sql import select as sql_select

from agent_os.core.config import get_garden_strong_edge_threshold
from agent_os.garden.models import KnowledgeCardLink, DailyInsight, InsightStatus
from agent_os.items.models import Item


class ClusterService:
    """Service for computing cluster strength.

    Formula:
    cluster_strength = strong_edges_count + (avg_relation_strength * 2.0) + (1.0 / (avg_days_between_nodes + 1))
    """

    def __init__(self, db: AsyncSession):
        """Initialize cluster service.

        Args:
            db: Async database session
        """
        self.db = db

    async def compute_cluster_strength(
        self,
        node_ids: List[str],
        workspace_id: str
    ) -> float:
        """Compute cluster strength for a set of nodes.

        Args:
            node_ids: List of node/item UUIDs in the cluster
            workspace_id: Workspace UUID

        Returns:
            float: Cluster strength score
        """
        workspace_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
        node_uuids = [uuid.UUID(nid) if isinstance(nid, str) else nid for nid in node_ids]

        if len(node_uuids) < 2:
            # Single node or empty cluster has strength based on self-loops only
            return await self._compute_single_node_strength(node_uuids, workspace_uuid)

        # Query edges within the cluster
        stmt = select(
            KnowledgeCardLink.relation_strength,
            KnowledgeCardLink.created_at
        ).where(
            and_(
                KnowledgeCardLink.workspace_id == workspace_uuid,
                KnowledgeCardLink.from_id.in_(node_uuids),
                KnowledgeCardLink.to_id.in_(node_uuids),
                KnowledgeCardLink.is_active == True
            )
        )
        result = await self.db.execute(stmt)
        edges = result.all()

        if not edges:
            return 0.0

        # Calculate components
        strong_edges_count = 0
        total_strength = 0.0
        threshold = get_garden_strong_edge_threshold()

        # Track unique edges for deduplication
        unique_edges = set()
        edge_dates = []

        for relation_strength, created_at in edges:
            total_strength += relation_strength or 0.0

            if (relation_strength or 0.0) >= threshold:
                # For strong edge count, deduplicate undirected edges
                # We need from_id and to_id for this, so we query again
                pass

        # Re-query with from_id and to_id for accurate strong edge counting
        stmt_full = select(
            KnowledgeCardLink.from_id,
            KnowledgeCardLink.to_id,
            KnowledgeCardLink.relation_strength,
            KnowledgeCardLink.created_at
        ).where(
            and_(
                KnowledgeCardLink.workspace_id == workspace_uuid,
                KnowledgeCardLink.from_id.in_(node_uuids),
                KnowledgeCardLink.to_id.in_(node_uuids),
                KnowledgeCardLink.is_active == True
            )
        )
        result_full = await self.db.execute(stmt_full)
        edges_full = result_full.all()

        unique_strong_edges = set()
        all_dates = []

        for from_id, to_id, relation_strength, created_at in edges_full:
            all_dates.append(created_at)

            if (relation_strength or 0.0) >= threshold:
                # Normalize edge direction for deduplication
                normalized = tuple(sorted([str(from_id), str(to_id)]))
                unique_strong_edges.add(normalized)

        strong_edges_count = len(unique_strong_edges)
        avg_relation_strength = total_strength / len(edges_full) if edges_full else 0.0

        # Calculate average days between nodes
        avg_days_between_nodes = await self._calculate_avg_days_between_nodes(
            node_uuids, all_dates
        )

        # Apply formula
        cluster_strength = (
            strong_edges_count +
            (avg_relation_strength * 2.0) +
            (1.0 / (avg_days_between_nodes + 1))
        )

        return cluster_strength

    async def _compute_single_node_strength(
        self,
        node_ids: List[uuid.UUID],
        workspace_id: uuid.UUID
    ) -> float:
        """Compute strength for single node or empty cluster."""
        if not node_ids:
            return 0.0

        # For single nodes, return base strength
        return 1.0 / 2.0  # 0.5 base strength

    async def _calculate_avg_days_between_nodes(
        self,
        node_ids: List[uuid.UUID],
        edge_dates: List[datetime]
    ) -> float:
        """Calculate average days between node connections.

        Args:
            node_ids: List of node UUIDs
            edge_dates: List of edge creation dates

        Returns:
            float: Average days between nodes
        """
        if len(edge_dates) < 2:
            return 0.0

        # Sort dates
        sorted_dates = sorted([d for d in edge_dates if d is not None])

        if len(sorted_dates) < 2:
            return 0.0

        # Calculate time span
        total_days = (sorted_dates[-1] - sorted_dates[0]).days

        # Average days between connections
        return total_days / (len(sorted_dates) - 1) if len(sorted_dates) > 1 else 0.0


class InsightWorker:
    """Worker for insight aggregation and status transitions.

    Handles:
    - Checking trigger conditions for status transition (candidate -> stable)
    - Deduplication by canonical_hash (evidence_count increment)
    - Source tracking
    """

    # Trigger thresholds
    MIN_SOURCES = 3
    MIN_TIMESPAN_DAYS = 3
    MIN_CLUSTER_STRENGTH = 2.5

    def __init__(self, db: AsyncSession, cluster_service: ClusterService = None):
        """Initialize insight worker.

        Args:
            db: Async database session
            cluster_service: Optional ClusterService for strength calculation
        """
        self.db = db
        self.cluster_service = cluster_service or ClusterService(db)

    async def process_candidate_insight(
        self,
        insight_id: str,
        source_item_ids: List[str],
        workspace_id: str
    ) -> Dict[str, Any]:
        """Process a candidate insight and potentially transition to stable.

        Args:
            insight_id: Insight UUID
            source_item_ids: List of source item UUIDs
            workspace_id: Workspace UUID

        Returns:
            dict: Processing result with status and details
        """
        insight_uuid = uuid.UUID(insight_id) if isinstance(insight_id, str) else insight_id
        workspace_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id

        # Get insight details
        stmt = select(DailyInsight).where(DailyInsight.id == insight_uuid)
        result = await self.db.execute(stmt)
        insight = result.scalar_one_or_none()

        if not insight:
            return {"success": False, "error": "Insight not found"}

        if insight.status != "candidate":
            return {"success": False, "error": f"Insight is not in candidate status (current: {insight.status})"}

        # Check trigger conditions
        conditions = await self._check_trigger_conditions(
            source_item_ids, workspace_uuid
        )

        if not conditions["met"]:
            return {
                "success": False,
                "status": "candidate",
                "reason": conditions["reason"],
                "conditions": conditions
            }

        # Transition to stable
        insight.status = "stable"
        insight.stability_score = min(1.0, conditions["cluster_strength"] / 5.0)

        await self.db.commit()

        return {
            "success": True,
            "status": "stable",
            "conditions": conditions
        }

    async def _check_trigger_conditions(
        self,
        source_item_ids: List[str],
        workspace_id: uuid.UUID
    ) -> Dict[str, Any]:
        """Check if trigger conditions are met.

        Conditions:
        - sources >= 3
        - timespan >= 3 days
        - cluster_strength >= 2.5

        Args:
            source_item_ids: List of source item UUIDs
            workspace_id: Workspace UUID

        Returns:
            dict: Condition check results
        """
        if len(source_item_ids) < self.MIN_SOURCES:
            return {
                "met": False,
                "reason": f"Insufficient sources: {len(source_item_ids)} < {self.MIN_SOURCES}"
            }

        # Query items to get creation dates
        node_uuids = [uuid.UUID(sid) if isinstance(sid, str) else sid for sid in source_item_ids]
        stmt = select(Item.created_at).where(Item.id.in_(node_uuids))
        result = await self.db.execute(stmt)
        dates = [row[0] for row in result.all() if row[0] is not None]

        if len(dates) < 2:
            timespan_days = 0
        else:
            timespan_days = (max(dates) - min(dates)).days

        if timespan_days < self.MIN_TIMESPAN_DAYS:
            return {
                "met": False,
                "reason": f"Insufficient timespan: {timespan_days} < {self.MIN_TIMESPAN_DAYS} days"
            }

        # Compute cluster strength
        cluster_strength = await self.cluster_service.compute_cluster_strength(
            source_item_ids, str(workspace_id)
        )

        if cluster_strength < self.MIN_CLUSTER_STRENGTH:
            return {
                "met": False,
                "reason": f"Cluster strength too low: {cluster_strength:.2f} < {self.MIN_CLUSTER_STRENGTH}"
            }

        return {
            "met": True,
            "sources_count": len(source_item_ids),
            "timespan_days": timespan_days,
            "cluster_strength": cluster_strength
        }

    async def upsert_insight_with_deduplication(
        self,
        workspace_id: str,
        user_id: str,
        canonical_hash: str,
        title: str,
        content: str,
        source_item_ids: List[str],
        level: int = 1
    ) -> Dict[str, Any]:
        """Create or update insight with deduplication by canonical_hash.

        If an insight with the same canonical_hash exists:
        - Increment evidence_count
        - Update source_item_ids (append new ones)
        - Do NOT create a new record

        Args:
            workspace_id: Workspace UUID
            user_id: User UUID
            canonical_hash: Hash for deduplication
            title: Insight title
            content: Insight content
            source_item_ids: List of source item UUIDs
            level: Insight level (1, 2, or 3)

        Returns:
            dict: Result with insight_id and action taken (created/updated)
        """
        workspace_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        # Check for existing insight with same canonical_hash
        stmt = select(DailyInsight).where(
            and_(
                DailyInsight.canonical_hash == canonical_hash,
                DailyInsight.user_id == user_uuid
            )
        )
        result = await self.db.execute(stmt)
        existing_insight = result.scalar_one_or_none()

        if existing_insight:
            # Update existing insight
            return await self._update_existing_insight(
                existing_insight, source_item_ids
            )
        else:
            # Create new insight
            return await self._create_new_insight(
                workspace_uuid, user_uuid, canonical_hash, title, content,
                source_item_ids, level
            )

    async def _update_existing_insight(
        self,
        insight: DailyInsight,
        new_source_item_ids: List[str]
    ) -> Dict[str, Any]:
        """Update existing insight with new evidence.

        Args:
            insight: Existing insight record
            new_source_item_ids: New source item IDs to add

        Returns:
            dict: Update result
        """
        # Increment evidence count
        insight.evidence_count = (insight.evidence_count or 1) + 1

        # Merge source item IDs (avoid duplicates)
        import json
        existing_sources = []
        if insight.source_item_ids:
            try:
                existing_sources = json.loads(insight.source_item_ids)
            except (json.JSONDecodeError, TypeError):
                existing_sources = []

        # Add new source IDs
        new_sources_set = set(str(sid) for sid in new_source_item_ids)
        merged_sources = list(set(existing_sources) | new_sources_set)
        insight.source_item_ids = json.dumps(merged_sources)

        # Update timestamp
        insight.updated_at = func.now()

        await self.db.commit()
        await self.db.refresh(insight)

        return {
            "success": True,
            "action": "updated",
            "insight_id": str(insight.id),
            "evidence_count": insight.evidence_count
        }

    async def _create_new_insight(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        canonical_hash: str,
        title: str,
        content: str,
        source_item_ids: List[str],
        level: int
    ) -> Dict[str, Any]:
        """Create new insight record.

        Args:
            workspace_id: Workspace UUID
            user_id: User UUID
            canonical_hash: Deduplication hash
            title: Insight title
            content: Insight content
            source_item_ids: Source item IDs
            level: Insight level

        Returns:
            dict: Creation result
        """
        import json

        insight = DailyInsight(
            workspace_id=workspace_id,
            user_id=user_id,
            title=title,
            content=content,
            status="candidate",  # Start as candidate
            level=level,
            canonical_hash=canonical_hash,
            stability_score=0.0,
            evidence_count=1,
            source_item_ids=json.dumps([str(sid) for sid in source_item_ids])
        )

        self.db.add(insight)
        await self.db.commit()
        await self.db.refresh(insight)

        return {
            "success": True,
            "action": "created",
            "insight_id": str(insight.id),
            "evidence_count": 1
        }

    @staticmethod
    def compute_canonical_hash(content: str) -> str:
        """Compute SHA-256 hash for deduplication.

        Args:
            content: Content to hash

        Returns:
            str: SHA-256 hex digest
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
