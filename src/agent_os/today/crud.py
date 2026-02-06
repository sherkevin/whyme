"""CRUD operations for Today module.

The Today module aggregates items that need user attention.
This is a simple implementation that returns active items from the workspace.
"""

import uuid
from typing import List, Dict, Any
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.items.models import Item, Workspace


async def get_today_view(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 50
) -> tuple[List[Item], Dict[str, Any]]:
    """Get items for the Today view.

    Args:
        db: Database session
        workspace_id: Workspace ID
        user_id: User ID
        limit: Maximum number of items to return

    Returns:
        Tuple of (items list, summary statistics)
    """
    # Get active items from the workspace
    # In a simple implementation, we return all active items
    # In a more advanced version, this could filter by:
    # - Items created/updated today
    # - Items with upcoming due dates
    # - Items marked as high priority
    # - Items from specific projects/areas

    query = (
        select(Item)
        .filter(
            and_(
                Item.workspace_id == workspace_id,
                Item.status == "active"
            )
        )
        .order_by(desc(Item.updated_at))
        .limit(limit)
    )

    result = await db.execute(query)
    items = result.scalars().all()

    # Build summary statistics
    summary = {
        "total_items": len(items),
        "by_type": {},
        "by_status": {},
        "recent_items": 0
    }

    for item in items:
        # Count by type
        item_type = item.type or "unknown"
        summary["by_type"][item_type] = summary["by_type"].get(item_type, 0) + 1

        # Count by status
        item_status = item.status or "unknown"
        summary["by_status"][item_status] = summary["by_status"].get(item_status, 0) + 1

        # Count recent items (updated in last 24 hours)
        if item.updated_at:
            from datetime import timedelta
            if item.updated_at > (datetime.now() - timedelta(days=1)):
                summary["recent_items"] += 1

    return list(items), summary
