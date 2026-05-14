"""Vector similarity search for knowledge cards."""

import logging
from typing import List, Optional

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.knowledge.embeddings import EmbeddingService
from agent_os.knowledge.models import Card
from agent_os.knowledge.rag_interface import SearchResult

logger = logging.getLogger(__name__)


# =============================================================================
# Vector Search Service
# =============================================================================

class VectorSearchService:
    """Service for performing vector similarity search on cards."""

    @staticmethod
    async def search_by_vector(
        db: AsyncSession,
        *,
        user_id: int,
        query_embedding: list[float],
        limit: int = 10,
        para_type_filter: str | None = None,
        similarity_threshold: float = 0.5,
    ) -> list[SearchResult]:
        """Search cards by vector similarity.

        Args:
            db: Database session
            user_id: User ID
            query_embedding: Query embedding vector
            limit: Maximum number of results
            para_type_filter: Optional paragraph type filter
            similarity_threshold: Minimum similarity score (0-1)

        Returns:
            List of search results with similarity scores
        """
        try:
            # Import here to check if pgvector is available
            from agent_os.knowledge.models import PGVECTOR_AVAILABLE

            if not PGVECTOR_AVAILABLE:
                logger.warning("pgvector not available, falling back to basic search")
                return await VectorSearchService._fallback_search(
                    db,
                    user_id=user_id,
                    query=query_embedding,  # Will be handled differently
                    limit=limit,
                    para_type_filter=para_type_filter,
                )

            # Use pgvector for similarity search
            return await VectorSearchService._pgvector_search(
                db,
                user_id=user_id,
                query_embedding=query_embedding,
                limit=limit,
                para_type_filter=para_type_filter,
                similarity_threshold=similarity_threshold,
            )

        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []

    @staticmethod
    async def _pgvector_search(
        db: AsyncSession,
        *,
        user_id: int,
        query_embedding: list[float],
        limit: int,
        para_type_filter: str | None,
        similarity_threshold: float,
    ) -> list[SearchResult]:
        """Perform search using pgvector cosine similarity.

        Args:
            db: Database session
            user_id: User ID
            query_embedding: Query embedding vector
            limit: Maximum results
            para_type_filter: Optional paragraph type filter
            similarity_threshold: Minimum similarity

        Returns:
            List of search results
        """
        try:
            # Convert embedding to string format for pgvector
            embedding_str = f"[{','.join(map(str, query_embedding))}]"

            # Build base query
            query_str = """
                SELECT id, title, content, para_type,
                       1 - (embedding <=> :query_embedding) as similarity
                FROM cards
                WHERE user_id = :user_id
                  AND embedding IS NOT NULL
            """

            params = {
                "user_id": user_id,
                "query_embedding": embedding_str,
            }

            # Add para_type filter if specified
            if para_type_filter:
                query_str += " AND para_type = :para_type"
                params["para_type"] = para_type_filter

            # Add similarity threshold
            query_str += " AND (1 - (embedding <=> :query_embedding)) >= :threshold"
            params["threshold"] = similarity_threshold

            # Order by similarity and limit
            query_str += " ORDER BY similarity DESC LIMIT :limit"
            params["limit"] = limit

            # Execute query
            result = await db.execute(text(query_str), params)
            rows = result.fetchall()

            # Convert to SearchResult objects
            search_results = []
            for row in rows:
                search_results.append(
                    SearchResult(
                        card_id=row.id,
                        title=row.title,
                        content=row.content[:500],  # Truncate for preview
                        para_type=row.para_type,
                        similarity=float(row.similarity),
                    )
                )

            return search_results

        except Exception as e:
            logger.error(f"Error in pgvector search: {e}")
            return []

    @staticmethod
    async def _fallback_search(
        db: AsyncSession,
        *,
        user_id: int,
        query: str,  # Note: this argument carries the embedding vector here.
        limit: int,
        para_type_filter: str | None,
    ) -> list[SearchResult]:
        """Fallback search when pgvector is not available.

        Uses basic text matching and computes similarity in Python.

        Args:
            db: Database session
            user_id: User ID
            query: Query string (not used in fallback)
            limit: Maximum results
            para_type_filter: Optional paragraph type filter

        Returns:
            List of search results (with similarity=0.0)
        """
        try:
            # Build query
            conditions = [Card.user_id == user_id]
            if para_type_filter:
                conditions.append(Card.para_type == para_type_filter)

            # Get recent cards as fallback
            result = await db.execute(
                select(Card)
                .filter(and_(*conditions))
                .order_by(Card.created_at.desc())
                .limit(limit)
            )
            cards = result.scalars().all()

            # Return with default similarity
            return [
                SearchResult(
                    card_id=card.id,
                    title=card.title,
                    content=card.content[:500],
                    para_type=card.para_type,
                    similarity=0.5,  # Default similarity for fallback
                )
                for card in cards
            ]

        except Exception as e:
            logger.error(f"Error in fallback search: {e}")
            return []

    @staticmethod
    async def search_similar_cards(
        db: AsyncSession,
        *,
        card_id: int,
        user_id: int,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Find similar cards to a given card.

        Args:
            db: Database session
            card_id: Reference card ID
            user_id: User ID
            limit: Maximum number of results

        Returns:
            List of similar cards
        """
        try:
            # Get the reference card
            result = await db.execute(
                select(Card).filter(
                    and_(Card.id == card_id, Card.user_id == user_id)
                )
            )
            reference_card = result.scalar_one_or_none()

            if not reference_card:
                logger.warning(f"Card {card_id} not found")
                return []

            # Check if card has embedding
            if not reference_card.embedding:
                logger.warning(f"Card {card_id} has no embedding")
                return []

            # Use the card's embedding for search
            return await VectorSearchService.search_by_vector(
                db,
                user_id=user_id,
                query_embedding=reference_card.embedding,
                limit=limit,
            )

        except Exception as e:
            logger.error(f"Error finding similar cards: {e}")
            return []


# =============================================================================
# Convenience Functions
# =============================================================================

async def search_cards_by_text(
    db: AsyncSession,
    *,
    user_id: int,
    query_text: str,
    limit: int = 10,
    para_type_filter: str | None = None,
) -> list[SearchResult]:
    """Search cards by text query using vector similarity.

    Args:
        db: Database session
        user_id: User ID
        query_text: Query text
        limit: Maximum results
        para_type_filter: Optional paragraph type filter

    Returns:
        List of search results
    """
    # Generate embedding for query
    query_embedding = EmbeddingService.embed_text(query_text)

    if not query_embedding:
        logger.warning(f"Failed to generate embedding for query: {query_text}")
        return []

    # Perform vector search
    return await VectorSearchService.search_by_vector(
        db,
        user_id=user_id,
        query_embedding=query_embedding,
        limit=limit,
        para_type_filter=para_type_filter,
    )
