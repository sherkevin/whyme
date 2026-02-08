"""Search Service - Manages search indices and indexing operations.

This module provides functionality for:
- Creating, updating, and deleting search indices
- Batch indexing operations
- Index rebuilding
- Automatic embedding generation
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from agent_os.search_engine.models import SearchIndex
from agent_os.search_engine.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class SearchService:
    """Service for managing search indices."""

    def __init__(self, db: AsyncSession, auto_embed: bool = True):
        """Initialize search service.

        Args:
            db: Database session
            auto_embed: Automatically generate embeddings for indexed items
        """
        self.db = db
        self.auto_embed = auto_embed
        self.embedding_service = get_embedding_service() if auto_embed else None

    # =========================================================================
    # Index Management
    # =========================================================================

    async def index_item(
        self,
        item_type: str,
        item_id: Union[str, uuid.UUID],
        title: str,
        content: str = None,
        tags: List[str] = None,
        search_metadata: Dict[str, Any] = None,
        embedding: List[float] = None,
        generate_embedding: bool = None
    ) -> SearchIndex:
        """Create or update a search index entry.

        Args:
            item_type: Type of the item ('card', 'task', 'note', etc.)
            item_id: UUID of the item (str or UUID object)
            title: Title of the item
            content: Main content for full-text search
            tags: List of tags for filtering
            search_metadata: Additional metadata for filtering
            embedding: Optional vector embedding for semantic search
            generate_embedding: Override auto_embed setting

        Returns:
            Created or updated SearchIndex object
        """
        # Normalize item_id to UUID
        if isinstance(item_id, str):
            item_uuid = uuid.UUID(item_id)
        elif isinstance(item_id, uuid.UUID):
            item_uuid = item_id
        else:
            raise TypeError(f"item_id must be str or UUID, got {type(item_id)}")

        # Generate embedding if not provided and auto_embed is enabled
        if embedding is None:
            should_generate = generate_embedding if generate_embedding is not None else self.auto_embed
            if should_generate and self.embedding_service:
                # Combine title and content for embedding
                text_for_embedding = f"{title}. {content or ''}"
                try:
                    embedding = await self.embedding_service.generate_embedding(text_for_embedding)
                    logger.debug(f"Generated embedding for {item_type}:{item_uuid}")
                except Exception as e:
                    logger.warning(f"Failed to generate embedding: {e}")
                    embedding = None

        # Check if index already exists
        stmt = select(SearchIndex).where(
            and_(
                SearchIndex.item_type == item_type,
                SearchIndex.item_id == item_uuid
            )
        )

        result = await self.db.execute(stmt)
        index = result.scalar_one_or_none()

        if index:
            # Update existing index
            index.title = title
            index.content = content
            index.tags = tags or []
            index.search_metadata = search_metadata or {}
            if embedding is not None:
                index.embedding = embedding
            index.updated_at = None  # Will be set by onupdate
            logger.info(f"Updated search index for {item_type}:{item_uuid}")
        else:
            # Create new index
            index = SearchIndex(
                item_type=item_type,
                item_id=item_uuid,
                title=title,
                content=content,
                tags=tags or [],
                search_metadata=search_metadata or {}
            )
            if embedding is not None:
                index.embedding = embedding
            self.db.add(index)
            logger.info(f"Created search index for {item_type}:{item_uuid}")

        await self.db.commit()
        await self.db.refresh(index)

        return index

    async def get_index(
        self,
        item_type: str,
        item_id: Union[str, uuid.UUID]
    ) -> Optional[SearchIndex]:
        """Get a search index by item type and ID.

        Args:
            item_type: Type of the item
            item_id: UUID of the item (str or UUID object)

        Returns:
            SearchIndex object or None
        """
        # Normalize item_id to UUID
        if isinstance(item_id, str):
            item_uuid = uuid.UUID(item_id)
        else:
            item_uuid = item_id

        stmt = select(SearchIndex).where(
            and_(
                SearchIndex.item_type == item_type,
                SearchIndex.item_id == item_uuid
            )
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_index(
        self,
        item_type: str,
        item_id: Union[str, uuid.UUID]
    ) -> bool:
        """Delete a search index.

        Args:
            item_type: Type of the item
            item_id: UUID of the item (str or UUID object)

        Returns:
            True if deleted, False if not found
        """
        # Normalize item_id to UUID
        if isinstance(item_id, str):
            item_uuid = uuid.UUID(item_id)
        else:
            item_uuid = item_id

        stmt = select(SearchIndex).where(
            and_(
                SearchIndex.item_type == item_type,
                SearchIndex.item_id == item_uuid
            )
        )

        result = await self.db.execute(stmt)
        index = result.scalar_one_or_none()

        if not index:
            return False

        await self.db.delete(index)
        await self.db.commit()

        logger.info(f"Deleted search index for {item_type}:{item_uuid}")
        return True

    async def bulk_index_items(
        self,
        items: List[Dict[str, Any]]
    ) -> int:
        """Create or update multiple search indices in bulk.

        Args:
            items: List of items to index, each containing:
                {
                    "item_type": str,
                    "item_id": str,
                    "title": str,
                    "content": str (optional),
                    "tags": List[str] (optional),
                    "search_metadata": Dict (optional),
                    "embedding": List[float] (optional)
                }

        Returns:
            Number of items indexed
        """
        indexed_count = 0

        for item_data in items:
            try:
                await self.index_item(
                    item_type=item_data["item_type"],
                    item_id=item_data["item_id"],
                    title=item_data["title"],
                    content=item_data.get("content"),
                    tags=item_data.get("tags"),
                    search_metadata=item_data.get("search_metadata"),
                    embedding=item_data.get("embedding")
                )
                indexed_count += 1
            except Exception as e:
                logger.error(f"Failed to index item {item_data.get('item_id')}: {e}")
                continue

        logger.info(f"Bulk indexed {indexed_count}/{len(items)} items")
        return indexed_count

    async def rebuild_index(
        self,
        item_type: Optional[str] = None
    ) -> int:
        """Rebuild search index from source data.

        For now, this is a simplified implementation that updates
        the updated_at timestamp. In production, this would:
        1. Query source items (Cards, Tasks, etc.)
        2. Regenerate embeddings
        3. Update all indices

        Args:
            item_type: Optional item type filter

        Returns:
            Number of indices rebuilt
        """
        # Query all indices matching the type
        stmt = select(SearchIndex)

        if item_type:
            stmt = stmt.where(SearchIndex.item_type == item_type)

        result = await self.db.execute(stmt)
        indices = result.scalars().all()

        count = 0
        for index in indices:
            # Update to trigger updated_at
            index.updated_at = None  # Will be set by onupdate
            count += 1

        await self.db.commit()

        logger.info(f"Rebuilt {count} search indices for type={item_type or 'all'}")
        return count

    # =========================================================================
    # Index Query
    # =========================================================================

    async def list_indices(
        self,
        item_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[SearchIndex]:
        """List search indices with optional filtering.

        Args:
            item_type: Filter by item type
            limit: Max results
            offset: Pagination offset

        Returns:
            List of SearchIndex objects
        """
        stmt = select(SearchIndex)

        if item_type:
            stmt = stmt.where(SearchIndex.item_type == item_type)

        stmt = stmt.order_by(SearchIndex.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_index_stats(
        self,
        item_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get statistics about search indices.

        Args:
            item_type: Optional item type filter

        Returns:
            Statistics dictionary
        """
        from sqlalchemy import func

        # Count indices by type
        stmt = select(
            SearchIndex.item_type,
            func.count(SearchIndex.id)
        ).group_by(SearchIndex.item_type)

        result = await self.db.execute(stmt)
        rows = result.all()

        stats = {
            "by_type": {row[0]: row[1] for row in rows},
            "total": sum(row[1] for row in rows)
        }

        # Get total count with filters
        count_stmt = select(func.count(SearchIndex.id))
        if item_type:
            count_stmt = count_stmt.where(SearchIndex.item_type == item_type)

        count_result = await self.db.execute(count_stmt)
        stats["filtered_total"] = count_result.scalar() or 0

        return stats
