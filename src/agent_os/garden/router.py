"""Garden API router.

Provides REST API endpoints for the Garden knowledge graph:
- Nodes list with filtering and pagination
- Edges batch query for strong connections
- Node detail with connected nodes
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, distinct
from sqlalchemy.orm import selectinload

from agent_os.db.base import get_db
from agent_os.auth.dependencies import get_current_user
from agent_os.auth.models import User
from agent_os.items.models import Item, Workspace
from agent_os.garden.models import KnowledgeCardLink, RelationType
from agent_os.garden.schema import (
    GardenNode,
    GardenNodeListResponse,
    GardenEdgeBatchRequest,
    GardenEdge,
    GardenEdgeBatchResponse,
    GardenNodeDetail,
    ConnectedNode,
    GardenErrorResponse,
)
from agent_os.garden.stats_service import GardenStatsService
from agent_os.core.config import get_garden_strong_edge_threshold

router = APIRouter(prefix="/api/v1/garden", tags=["Garden"])


# ============================================================================
# Helper Functions
# ============================================================================

async def verify_workspace_access(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID
) -> Workspace:
    """Verify user has access to workspace.

    Args:
        db: Database session
        user_id: User UUID
        workspace_id: Workspace UUID

    Returns:
        Workspace object

    Raises:
        HTTPException: If workspace not found or access denied
    """
    workspace = await db.get(Workspace, workspace_id)

    if not workspace or workspace.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or access denied"
        )

    return workspace


def get_item_jump_url(item_id: uuid.UUID) -> str:
    """Generate jump URL for an item.

    Args:
        item_id: Item UUID

    Returns:
        URL string
    """
    return f"/items/{item_id}"


# ============================================================================
# Garden Nodes API
# ============================================================================

@router.get(
    "/nodes",
    response_model=GardenNodeListResponse,
    responses={
        401: {"model": GardenErrorResponse, "description": "Not authenticated"},
        404: {"model": GardenErrorResponse, "description": "Workspace not found"}
    }
)
async def list_garden_nodes(
    workspace_id: uuid.UUID = Query(..., description="Workspace ID to filter nodes"),
    date_range: Optional[str] = Query(
        None,
        description="Date range filter: 'last_7_days', 'last_30_days', 'last_90_days', 'all'"
    ),
    types: Optional[List[str]] = Query(
        None,
        description="Filter by item types (e.g., 'note', 'card', 'task')"
    ),
    limit: int = Query(300, ge=1, le=1000, description="Maximum items to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get Garden nodes list.

    Returns a paginated list of nodes (items) in the garden knowledge graph.
    Supports filtering by date range and types.

    **Performance**: Uses efficient SQL queries with proper indexing.
    """
    # Verify workspace access
    await verify_workspace_access(db, current_user.id, workspace_id)

    # Build base query - select items with strong connection count
    stmt = select(
        Item.id,
        Item.type,
        Item.title,
        Item.created_at,
        Item.content,
        func.count(distinct(KnowledgeCardLink.id)).label("strong_connection_count")
    ).outerjoin(
        KnowledgeCardLink,
        and_(
            KnowledgeCardLink.from_id == Item.id,
            KnowledgeCardLink.relation_strength >= get_garden_strong_edge_threshold(),
            KnowledgeCardLink.is_active == True
        )
    ).where(
        and_(
            Item.workspace_id == workspace_id,
            Item.status == "active"
        )
    ).group_by(
        Item.id, Item.type, Item.title, Item.created_at, Item.content
    )

    # Apply date range filter
    if date_range:
        now = datetime.utcnow()
        if date_range == "last_7_days":
            stmt = stmt.where(Item.created_at >= now - timedelta(days=7))
        elif date_range == "last_30_days":
            stmt = stmt.where(Item.created_at >= now - timedelta(days=30))
        elif date_range == "last_90_days":
            stmt = stmt.where(Item.created_at >= now - timedelta(days=90))
        # 'all' or unknown values return all items

    # Apply types filter
    if types:
        stmt = stmt.where(Item.type.in_(types))

    # Get total count before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Apply pagination
    stmt = stmt.order_by(Item.created_at.desc()).offset(offset).limit(limit)

    # Execute query
    result = await db.execute(stmt)
    rows = result.all()

    # Convert to response models
    nodes = [
        GardenNode(
            id=row.id,
            object_type=row.type,
            title=row.title,
            created_at=row.created_at,
            strong_connection_count=row.strong_connection_count,
            snippet=row.content[:200] + "..." if row.content and len(row.content) > 200 else row.content
        )
        for row in rows
    ]

    return GardenNodeListResponse(
        data=nodes,
        total=total,
        limit=limit,
        offset=offset
    )


# ============================================================================
# Garden Edges API
# ============================================================================

@router.post(
    "/edges/batch",
    response_model=GardenEdgeBatchResponse,
    responses={
        401: {"model": GardenErrorResponse, "description": "Not authenticated"},
        422: {"model": GardenErrorResponse, "description": "Validation error"}
    }
)
async def batch_query_edges(
    request: GardenEdgeBatchRequest,
    workspace_id: uuid.UUID = Query(..., description="Workspace ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Query strong edges between specified nodes.

    Returns edges where BOTH from_id and to_id are in the provided node_ids list.
    Only strong edges (relation_strength >= threshold) are returned.

    **Performance**: Single query with IN clause, no N+1 issues.
    """
    # Verify workspace access
    await verify_workspace_access(db, current_user.id, workspace_id)

    if not request.node_ids:
        return GardenEdgeBatchResponse(
            data=[],
            connections_count=0,
            metadata={"message": "No node IDs provided"}
        )

    # Convert to string list for comparison
    node_id_strs = [str(nid) for nid in request.node_ids]

    # Query strong edges where both endpoints are in the list
    # Use single query for performance (no N+1)
    threshold = get_garden_strong_edge_threshold()

    stmt = select(KnowledgeCardLink).where(
        and_(
            KnowledgeCardLink.workspace_id == workspace_id,
            KnowledgeCardLink.from_id.in_(request.node_ids),
            KnowledgeCardLink.to_id.in_(request.node_ids),
            KnowledgeCardLink.relation_strength >= threshold,
            KnowledgeCardLink.is_active == True
        )
    )

    result = await db.execute(stmt)
    edges = result.scalars().all()

    # Convert to response models
    edge_list = [
        GardenEdge(
            id=edge.id,
            from_id=edge.from_id,
            to_id=edge.to_id,
            type=edge.type or "related",
            relation_strength=edge.relation_strength or 0.0,
            created_at=edge.created_at
        )
        for edge in edges
    ]

    return GardenEdgeBatchResponse(
        data=edge_list,
        connections_count=len(edge_list),
        metadata={
            "threshold": threshold,
            "requested_nodes": len(request.node_ids)
        }
    )


# ============================================================================
# Garden Node Detail API
# ============================================================================

@router.get(
    "/nodes/{node_id}",
    response_model=GardenNodeDetail,
    responses={
        401: {"model": GardenErrorResponse, "description": "Not authenticated"},
        404: {"model": GardenErrorResponse, "description": "Node not found"}
    }
)
async def get_node_detail(
    node_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(..., description="Workspace ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a garden node.

    Returns full node details plus up to 5 connected nodes,
    sorted by relation_strength in descending order.

    **Performance**: Uses eager loading to avoid N+1 queries.
    """
    # Verify workspace access
    await verify_workspace_access(db, current_user.id, workspace_id)

    # Get the node
    node = await db.get(Item, node_id)

    if not node or node.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node not found"
        )

    # Get connected nodes (up to 5, sorted by relation_strength desc)
    # Single query - no N+1
    threshold = get_garden_strong_edge_threshold()

    stmt = (
        select(
            Item.id,
            Item.type,
            Item.title,
            KnowledgeCardLink.relation_strength
        )
        .join(
            KnowledgeCardLink,
            or_(
                and_(KnowledgeCardLink.from_id == node_id, KnowledgeCardLink.to_id == Item.id),
                and_(KnowledgeCardLink.to_id == node_id, KnowledgeCardLink.from_id == Item.id)
            )
        )
        .where(
            and_(
                KnowledgeCardLink.workspace_id == workspace_id,
                KnowledgeCardLink.is_active == True,
                KnowledgeCardLink.relation_strength >= threshold,
                Item.status == "active"
            )
        )
        .order_by(KnowledgeCardLink.relation_strength.desc())
        .limit(5)
    )

    result = await db.execute(stmt)
    connected_rows = result.all()

    connected_nodes = [
        ConnectedNode(
            id=row.id,
            title=row.title,
            object_type=row.type,
            relation_strength=row.relation_strength or 0.0,
            jump_url=get_item_jump_url(row.id)
        )
        for row in connected_rows
    ]

    # Build detail response
    return GardenNodeDetail(
        id=node.id,
        object_type=node.type,
        title=node.title,
        type=node.type,
        time=node.created_at,
        summary=node.content[:500] if node.content else None,
        jump_url=get_item_jump_url(node.id),
        connected_nodes=connected_nodes
    )
