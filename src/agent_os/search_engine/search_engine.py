"""Search Engine - Executes search queries and ranks results.

This module implements the core search functionality including:
- Full-text search (PostgreSQL or SQLite LIKE)
- Vector semantic search (using embeddings)
- Hybrid search (text + vector)
- Result ranking and scoring
- Filtering and pagination
"""

import uuid
import logging
import math
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from agent_os.search_engine.models import SearchIndex
from agent_os.search_engine.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class SearchResult:
    """Search result container."""

    def __init__(
        self,
        total: int,
        page: int,
        page_size: int,
        results: List["SearchResultItem"]
    ):
        self.total = total
        self.page = page
        self.page_size = page_size
        self.results = results


class SearchResultItem:
    """Single search result item."""

    def __init__(
        self,
        item_type: str,
        item_id: str,
        title: str,
        content_snippet: str,
        score: float,
        tags: List[str],
        search_metadata: Dict,
        created_at
    ):
        self.item_type = item_type
        self.item_id = item_id
        self.title = title
        self.content_snippet = content_snippet
        self.score = score
        self.tags = tags
        self.search_metadata = search_metadata
        self.created_at = created_at


class SearchQuery:
    """Search query parameters."""

    def __init__(
        self,
        query: str,
        item_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        date_from: Optional = None,
        date_to: Optional = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "relevance",
        include_vectors: bool = False
    ):
        self.query = query
        self.item_types = item_types or []
        self.tags = tags or []
        self.date_from = date_from
        self.date_to = date_to
        self.page = page
        self.page_size = page_size
        self.sort_by = sort_by
        self.include_vectors = include_vectors


class SearchEngine:
    """Search Engine - Executes search queries and ranks results."""

    def __init__(self, db: AsyncSession, enable_vector_search: bool = False):
        """Initialize search engine.

        Args:
            db: Database session
            enable_vector_search: Enable semantic vector search (default: False for compatibility)
        """
        self.db = db
        self.enable_vector_search = enable_vector_search
        self.embedding_service = get_embedding_service() if enable_vector_search else None

    async def search(
        self,
        search_query: SearchQuery
    ) -> SearchResult:
        """Execute a search query.

        Args:
            search_query: SearchQuery parameters

        Returns:
            SearchResult with ranked results
        """
        # Perform text search
        text_result = await self._text_search(search_query)

        # If vector search is enabled and we have embeddings, perform semantic search
        if self.enable_vector_search and self.embedding_service:
            try:
                # Generate query embedding
                query_embedding = await self.embedding_service.generate_embedding(search_query.query)

                # Get all results with embeddings
                stmt = select(SearchIndex).where(
                    SearchIndex.embedding.isnot(None)
                )

                # Apply same filters as text search
                where_clauses = []
                if search_query.item_types:
                    where_clauses.append(SearchIndex.item_type.in_(search_query.item_types))
                if search_query.tags:
                    # Note: tag filtering done in Python for SQLite
                    pass
                if search_query.date_from:
                    where_clauses.append(SearchIndex.created_at >= search_query.date_from)
                if search_query.date_to:
                    where_clauses.append(SearchIndex.created_at <= search_query.date_to)

                if where_clauses:
                    stmt = stmt.where(and_(*where_clauses))

                result = await self.db.execute(stmt)
                all_rows = result.scalars().all()

                # Calculate cosine similarities
                vector_scores = []
                for row in all_rows:
                    if row.embedding:
                        similarity = self._cosine_similarity(query_embedding, row.embedding)
                        vector_scores.append({
                            'row': row,
                            'similarity': similarity
                        })

                # Sort by similarity and get top results
                vector_scores.sort(key=lambda x: x['similarity'], reverse=True)

                # Merge text and vector results (hybrid search)
                merged_result = self._merge_results(text_result, vector_scores, search_query)

                return merged_result

            except Exception as e:
                logger.warning(f"Vector search failed, falling back to text-only: {e}")
                return text_result

        return text_result

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score
        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _merge_results(
        self,
        text_result: SearchResult,
        vector_scores: List[Dict],
        query: SearchQuery
    ) -> SearchResult:
        """Merge text and vector search results.

        Args:
            text_result: Text search results
            vector_scores: Vector search results with scores
            query: Original search query

        Returns:
            Merged search result
        """
        # Create mapping of item_id to text score
        text_scores = {}
        for item in text_result.results:
            key = (item.item_type, item.item_id)
            text_scores[key] = item.score

        # Combine scores (weighted average: 0.6 text + 0.4 vector)
        seen = set()
        merged_items = []

        for vector_item in vector_scores[:query.page_size * 2]:  # Get more to account for overlap
            row = vector_item['row']
            key = (row.item_type, str(row.item_id))

            if key in seen:
                continue
            seen.add(key)

            text_score = text_scores.get(key, 0.0)
            vector_score = vector_item['similarity']

            # Hybrid score: weighted combination
            combined_score = 0.6 * text_score + 0.4 * vector_score

            # Generate snippet
            snippet = self._generate_snippet(row.content, query.query)

            merged_items.append(SearchResultItem(
                item_type=row.item_type,
                item_id=str(row.item_id),
                title=row.title,
                content_snippet=snippet,
                score=combined_score,
                tags=row.tags or [],
                search_metadata=row.search_metadata or {},
                created_at=row.created_at
            ))

        # Add any text-only results that weren't in vector results
        for item in text_result.results:
            key = (item.item_type, item.item_id)
            if key not in seen and len(merged_items) < query.page_size:
                seen.add(key)
                merged_items.append(item)

        # Paginate
        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        paginated_items = merged_items[start:end]

        return SearchResult(
            total=len(merged_items),
            page=query.page,
            page_size=query.page_size,
            results=paginated_items
        )

    async def _text_search(
        self,
        query: SearchQuery
    ) -> SearchResult:
        """Execute full-text search.

        For SQLite (testing), uses LIKE pattern matching.
        For PostgreSQL, would use tsvector.

        Args:
            query: SearchQuery parameters

        Returns:
            SearchResult with ranked results
        """
        # Build WHERE clause for LIKE search (SQLite compatible)
        search_term = f"%{query.query}%"

        where_clauses = [
            or_(
                SearchIndex.title.like(search_term),
                SearchIndex.content.like(search_term)
            )
        ]

        # Add filters using SQLAlchemy expressions
        if query.item_types:
            where_clauses.append(SearchIndex.item_type.in_(query.item_types))

        # Note: Tag filtering done in Python for SQLite compatibility
        if query.date_from:
            where_clauses.append(SearchIndex.created_at >= query.date_from)

        if query.date_to:
            where_clauses.append(SearchIndex.created_at <= query.date_to)

        # Build query
        stmt = select(SearchIndex).where(and_(*where_clauses))

        # Order by
        order_by = self._get_order_by(query.sort_by)
        stmt = stmt.order_by(order_by)

        # Execute search WITHOUT pagination first (to get all matching rows for tag filtering)
        result = await self.db.execute(stmt)
        all_rows = result.scalars().all()

        # Filter by tags in Python if needed (for SQLite compatibility)
        if query.tags:
            filtered_rows = []
            for row in all_rows:
                row_tags = row.tags or []
                if any(tag in row_tags for tag in query.tags):
                    filtered_rows.append(row)
            all_rows = filtered_rows

        # Total count after tag filtering
        total = len(all_rows)

        # Apply pagination AFTER tag filtering
        offset = (query.page - 1) * query.page_size
        paginated_rows = all_rows[offset:offset + query.page_size]

        # Build results
        results = []
        for row in paginated_rows:
            # Calculate score
            score = self._calculate_score(row, query.query)

            # Generate content snippet
            content_snippet = self._generate_snippet(row.content, query.query)

            results.append(SearchResultItem(
                item_type=row.item_type,
                item_id=str(row.item_id),
                title=row.title,
                content_snippet=content_snippet,
                score=score,
                tags=row.tags or [],
                search_metadata=row.search_metadata or {},
                created_at=row.created_at
            ))

        return SearchResult(
            total=total,
            page=query.page,
            page_size=query.page_size,
            results=results
        )

    def _get_order_by(self, sort_by: str) -> Any:
        """Get ORDER BY clause.

        Args:
            sort_by: Sort type

        Returns:
            SQLAlchemy order by expression
        """
        if sort_by == "-date":
            return SearchIndex.created_at.desc()
        elif sort_by == "date":
            return SearchIndex.created_at.asc()
        else:  # relevance
            # For SQLite, just sort by date (would use rank in PostgreSQL)
            return SearchIndex.created_at.desc()

    def _calculate_score(self, row: SearchIndex, query: str) -> float:
        """Calculate relevance score for a result.

        Args:
            row: SearchIndex row
            query: Search query string

        Returns:
            Score between 0 and 1
        """
        query_lower = query.lower()
        title_lower = row.title.lower()

        # Simple scoring: exact match in title = 1.0, contains = 0.5
        if query_lower in title_lower:
            return 1.0
        elif row.content and query_lower in row.content.lower():
            return 0.7
        else:
            return 0.5

    def _generate_snippet(self, content: Optional[str], query: str, max_length: int = 200) -> str:
        """Generate content snippet with query highlighting.

        Args:
            content: Original content
            query: Search query
            max_length: Maximum snippet length

        Returns:
            Snippet text
        """
        if not content:
            return ""

        # Find first occurrence of query in content
        content_lower = content.lower()
        query_lower = query.lower()

        index = content_lower.find(query_lower)

        if index == -1:
            # Query not found, return first N chars
            return content[:max_length] + ("..." if len(content) > max_length else "")

        # Return snippet centered around match
        start = max(0, index - 50)
        end = min(len(content), index + len(query) + 50)

        snippet = content[start:end]
        if len(content) > end:
            snippet += "..."

        return snippet

    async def delete_by_item(
        self,
        item_type: str,
        item_id: str
    ) -> bool:
        """Delete search index when item is deleted.

        Args:
            item_type: Type of the item
            item_id: UUID of the deleted item

        Returns:
            True if deleted
        """
        from agent_os.search_engine.search_service import SearchService
        service = SearchService(self.db)
        return await service.delete_index(item_type, item_id)

    async def delete_index(
        self,
        item_type: str,
        item_id: str
    ) -> bool:
        """Delete a search index.

        Args:
            item_type: Type of the item
            item_id: UUID of the item

        Returns:
            True if deleted
        """
        from agent_os.search_engine.search_service import SearchService
        service = SearchService(self.db)
        return await service.delete_index(item_type, item_id)
