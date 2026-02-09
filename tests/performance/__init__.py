"""Performance test utilities and helpers."""

import asyncio
from datetime import datetime
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.search_engine.models import SearchIndex
from agent_os.search_engine.search_service import SearchService
import uuid


async def seed_test_data(db: AsyncSession, num_items: int = 200):
    """Seed test data for performance testing.

    Args:
        db: Database session
        num_items: Number of test items to create
    """
    item_types = ["card", "task", "note", "resource"]
    tags_list = [
        ["important", "urgent"],
        ["work", "project-a"],
        ["personal", "ideas"],
        ["reference", "documentation"],
        ["bug", "fix-required"]
    ]

    for i in range(num_items):
        item_type = item_types[i % len(item_types)]
        tags = tags_list[i % len(tags_list)]

        index = SearchIndex(
            item_type=item_type,
            item_id=uuid.uuid4(),
            title=f"Test Item {i}: {item_type.capitalize()}",
            content=f"This is test content for item {i}. " * 10,
            tags=tags,
            search_metadata={
                "priority": i % 3,
                "status": "active"
            },
            # Required fields
            embedding=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(index)

    await db.commit()
    print(f"✓ Seeded {num_items} test items for performance testing")
