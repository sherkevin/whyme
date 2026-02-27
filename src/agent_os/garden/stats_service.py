"""Garden Stats Service - PRD8 Module 2.

Provides statistics aggregation for user's garden knowledge graph.
"""

import uuid
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, distinct
from sqlalchemy.sql import select as sql_select

from agent_os.core.config import get_garden_strong_edge_threshold
from agent_os.garden.models import KnowledgeCardLink, DailyInsight
from agent_os.items.models import Item


class GardenStatsService:
    """Service for computing user garden statistics.

    Provides methods to compute:
    - total_notes: Count of active notes/cards
    - neural_connections: Count of unique strong edges (undirected graph deduplication)
    - generated_insights: Count of stable insights with level >= 2 (deduplicated by canonical_hash)
    """

    def __init__(self, db: AsyncSession):
        """Initialize garden stats service.

        Args:
            db: Async database session
        """
        self.db = db

    async def get_user_garden_stats(
        self,
        user_id: str,
        workspace_id: str
    ) -> Dict[str, Any]:
        """Get garden statistics for a user.

        Args:
            user_id: User UUID
            workspace_id: Workspace UUID

        Returns:
            dict: Statistics including:
                - total_notes: Count of active notes/cards
                - neural_connections: Count of unique strong edges
                - generated_insights: Count of stable insights (level >= 2)
        """
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        workspace_uuid = uuid.UUID(workspace_id) if isinstance(workspace_id, str) else workspace_id

        # Compute all stats concurrently
        total_notes = await self._count_total_notes(workspace_uuid)
        neural_connections = await self._count_neural_connections(workspace_uuid)
        generated_insights = await self._count_generated_insights(user_uuid)

        return {
            "user_id": str(user_uuid),
            "workspace_id": str(workspace_uuid),
            "total_notes": total_notes,
            "neural_connections": neural_connections,
            "generated_insights": generated_insights,
        }

    async def _count_total_notes(self, workspace_id: uuid.UUID) -> int:
        """Count active notes/cards in workspace.

        Args:
            workspace_id: Workspace UUID

        Returns:
            int: Count of active notes
        """
        stmt = select(func.count(Item.id)).where(
            and_(
                Item.workspace_id == workspace_id,
                Item.status == "active"
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _count_neural_connections(self, workspace_id: uuid.UUID) -> int:
        """Count unique strong edges (undirected graph deduplication).

        Strong edges are those with relation_strength >= threshold.
        A-B and B-A are considered the same connection (undirected graph).

        Args:
            workspace_id: Workspace UUID

        Returns:
            int: Count of unique strong connections
        """
        threshold = get_garden_strong_edge_threshold()

        # Query all strong edges
        stmt = select(
            KnowledgeCardLink.from_id,
            KnowledgeCardLink.to_id
        ).where(
            and_(
                KnowledgeCardLink.workspace_id == workspace_id,
                KnowledgeCardLink.relation_strength >= threshold,
                KnowledgeCardLink.is_active == True
            )
        )
        result = await self.db.execute(stmt)
        edges = result.all()

        if not edges:
            return 0

        # Deduplicate: treat A-B and B-A as the same edge
        # Use frozenset to normalize direction
        unique_edges = set()
        for from_id, to_id in edges:
            # Create normalized edge (sorted tuple)
            normalized_edge = tuple(sorted([str(from_id), str(to_id)]))
            unique_edges.add(normalized_edge)

        return len(unique_edges)

    async def _count_generated_insights(self, user_id: uuid.UUID) -> int:
        """Count stable insights with level >= 2, deduplicated by canonical_hash.

        Args:
            user_id: User UUID

        Returns:
            int: Count of unique stable insights
        """
        # Query distinct canonical_hash for stable insights with level >= 2
        stmt = select(
            distinct(DailyInsight.canonical_hash)
        ).where(
            and_(
                DailyInsight.user_id == user_id,
                DailyInsight.status == "stable",
                DailyInsight.level >= 2,
                DailyInsight.canonical_hash.isnot(None)
            )
        )
        result = await self.db.execute(stmt)
        hashes = result.scalars().all()

        return len(hashes)
