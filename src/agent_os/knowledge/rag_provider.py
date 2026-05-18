"""Concrete RAG provider implementation using database."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_os.knowledge.models import Card
from agent_os.knowledge.rag_interface import (
    KnowledgeContext,
    RAGProvider,
    SearchResult,
)

# Try to import pgvector cosine_distance, but don't fail if not available
try:
    from pgvector.sqlalchemy import cosine_distance
    PGVECTOR_AVAILABLE = True
except ImportError:
    PGVECTOR_AVAILABLE = False

    def cosine_distance(left, right):
        return func.levenshtein(left, right)


class CardRAGProvider(RAGProvider):
    """RAG provider using Card model with vector embeddings."""

    def __init__(self, db_session: AsyncSession, embedding_model=None):
        """Initialize Card RAG provider.

        Args:
            db_session: Async database session
            embedding_model: Optional embedding model for generating vectors
        """
        self.db = db_session
        self.embedding_model = embedding_model

    async def search_knowledge(
        self,
        user_id: int,
        query: str,
        limit: int = 5,
        para_type: str | None = None,
        tags: list[str] | None = None
    ) -> list[SearchResult]:
        """Search knowledge base using vector similarity.

        Args:
            user_id: User ID
            query: Search query
            limit: Max results
            para_type: Filter by type
            tags: Filter by tags

        Returns:
            Search results sorted by relevance
        """
        # Build query
        query_obj = select(Card).filter(Card.user_id == user_id)

        # Add filters
        if para_type:
            query_obj = query_obj.filter(Card.para_type == para_type)

        if tags:
            query_obj = query_obj.filter(Card.tags.overlap(tags))

        # If we have embedding model and query, do vector search
        if self.embedding_model:
            # Generate query embedding
            query_embedding = await self.embedding_model.embed_query(query)

            # Vector similarity search
            query_obj = query_obj.order_by(
                cosine_distance(Card.embedding, query_embedding)
            )
        else:
            # Fallback: order by recent
            query_obj = query_obj.order_by(Card.created_at.desc())

        query_obj = query_obj.limit(limit)

        # Execute
        result = await self.db.execute(query_obj)
        cards = result.scalars().all()

        # Convert to SearchResult
        return [
            SearchResult(
                id=card.id,
                title=card.title,
                content=card.content,
                para_type=card.para_type,
                similarity=0.0,  # TODO: Calculate actual similarity
                metadata={
                    "tags": card.tags,
                    "created_at": card.created_at.isoformat()
                }
            )
            for card in cards
        ]

    async def add_knowledge(
        self,
        user_id: int,
        title: str,
        content: str,
        para_type: str,
        tags: list[str] = None,
        metadata: dict[str, Any] = None
    ) -> int:
        """Add knowledge card with optional embedding generation.

        Args:
            user_id: User ID
            title: Card title
            content: Card content
            para_type: Card type
            tags: Optional tags
            metadata: Optional metadata

        Returns:
            Created card ID
        """
        # Generate embedding if model available
        embedding = None
        if self.embedding_model:
            # Combine title and content for embedding
            text = f"{title}\n{content}"
            embedding = await self.embedding_model.embed_text(text)

        # Create card
        card = Card(
            user_id=user_id,
            title=title,
            content=content,
            para_type=para_type,
            tags=tags or [],
            embedding=embedding
        )

        self.db.add(card)
        await self.db.commit()
        await self.db.refresh(card)

        return card.id

    async def get_context_for_task(
        self,
        user_id: int,
        task_id: int,
        task_description: str
    ) -> KnowledgeContext:
        """Get relevant knowledge context for a task.

        Args:
            user_id: User ID
            task_id: Task ID
            task_description: Task description

        Returns:
            Formatted knowledge context
        """
        # Search relevant knowledge
        results = await self.search_knowledge(
            user_id=user_id,
            query=task_description,
            limit=5  # Top 5 most relevant
        )

        # Get user stats
        stats = await self.get_user_knowledge_stats(user_id)

        # Format context for AI
        formatted_context = self._format_context(results, task_description)

        return KnowledgeContext(
            query=task_description,
            results=results,
            formatted_context=formatted_context,
            total_cards=stats["total_cards"],
            user_id=user_id
        )

    async def get_user_knowledge_stats(
        self,
        user_id: int
    ) -> dict[str, Any]:
        """Get user's knowledge statistics.

        Args:
            user_id: User ID

        Returns:
            Statistics dictionary
        """
        # Total cards
        total_result = await self.db.execute(
            select(func.count(Card.id)).filter(Card.user_id == user_id)
        )
        total_cards = total_result.scalar_one()

        # Cards by type
        type_result = await self.db.execute(
            select(Card.para_type, func.count(Card.id))
            .filter(Card.user_id == user_id)
            .group_by(Card.para_type)
        )
        by_type = {row[0]: row[1] for row in type_result.all()}

        # Recently added (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.now() - timedelta(days=7)

        recent_result = await self.db.execute(
            select(func.count(Card.id))
            .filter(Card.user_id == user_id)
            .filter(Card.created_at >= week_ago)
        )
        recently_added = recent_result.scalar_one()

        return {
            "total_cards": total_cards,
            "by_type": by_type,
            "recently_added": recently_added
        }

    def _format_context(
        self,
        results: list[SearchResult],
        query: str
    ) -> str:
        """Format search results into context for AI.

        Args:
            results: Search results
            query: Original query

        Returns:
            Formatted context string
        """
        if not results:
            return f"# User Query: {query}\n\nNo relevant knowledge found."

        context_parts = [
            f"# User Query: {query}\n",
            f"# Relevant Knowledge ({len(results)} items)\n"
        ]

        for i, result in enumerate(results, 1):
            context_parts.append(f"""
## {i}. {result.title} (Type: {result.para_type})

{result.content}

**Tags**: {', '.join(result.metadata.get('tags', []))}
---
""")

        return "\n".join(context_parts)


def get_rag_provider(db_session: AsyncSession, embedding_model=None) -> RAGProvider:
    """Factory function to get RAG provider.

    This allows easy switching between different RAG implementations
    while keeping a single production integration point.

    Args:
        db_session: Database session
        embedding_model: Optional embedding model

    Returns:
        RAG provider instance
    """
    return CardRAGProvider(db_session, embedding_model)
