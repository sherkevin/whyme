"""CRUD operations for Today module.

The Today module aggregates items that need user attention.
This is a simple implementation that returns active items from the workspace.
"""

import uuid
from typing import Any, Dict, List

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.items.models import Item


async def get_today_view(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 50
) -> tuple[list[Item], dict[str, Any]]:
    """Get items for the Today view.

    PA 1.0 Stage 2: Returns PROCESSED items from Agent processing.

    Args:
        db: Database session
        workspace_id: Workspace ID
        user_id: User ID
        limit: Maximum number of items to return

    Returns:
        Tuple of (items list, summary statistics)
    """
    from datetime import datetime, timedelta

    from agent_os.items.models import ItemStatus

    # Get PROCESSED items from the workspace
    # Stage 2 requirement: Return items that have been processed by the Agent
    query = (
        select(Item)
        .filter(
            and_(
                Item.workspace_id == workspace_id,
                Item.status == ItemStatus.PROCESSED
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
        "recent_items": 0,
        "agent_processed": len(items)  # Track agent-processed items
    }

    for item in items:
        # Count by type
        item_type = item.item_type.value if item.item_type else "unknown"
        summary["by_type"][item_type] = summary["by_type"].get(item_type, 0) + 1

        # Count by status (all should be PROCESSED)
        item_status = item.status.value if item.status else "unknown"
        summary["by_status"][item_status] = summary["by_status"].get(item_status, 0) + 1

        # Count recent items (updated in last 24 hours)
        if item.updated_at:
            if item.updated_at > (datetime.now() - timedelta(days=1)):
                summary["recent_items"] += 1

    return list(items), summary
