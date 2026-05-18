"""RAG (Retrieval-Augmented Generation) interface layer.

This module provides an abstraction layer between the knowledge management
system and the AI agent, allowing them to evolve independently.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class SearchResult(BaseModel):
    """Single search result from knowledge base."""

    id: int
    title: str
    content: str
    para_type: str
    similarity: float
    metadata: dict[str, Any] = {}


class KnowledgeContext(BaseModel):
    """Aggregated knowledge context for AI agent."""

    query: str
    results: list[SearchResult]
    formatted_context: str
    total_cards: int
    user_id: int


class RAGProvider(ABC):
    """Abstract RAG provider interface.

    This interface decouples the knowledge management system from the AI agent,
    allowing them to evolve independently while maintaining a clean integration point.
    """

    @abstractmethod
    async def search_knowledge(
        self,
        user_id: int,
        query: str,
        limit: int = 5,
        para_type: str | None = None,
        tags: list[str] | None = None
    ) -> list[SearchResult]:
        """Search knowledge base by semantic similarity.

        Args:
            user_id: User ID for data isolation
            query: Search query text
            limit: Maximum number of results
            para_type: Optional filter by card type
            tags: Optional filter by tags

        Returns:
            List of search results sorted by relevance
        """
        pass

    @abstractmethod
    async def add_knowledge(
        self,
        user_id: int,
        title: str,
        content: str,
        para_type: str,
        tags: list[str] = None,
        metadata: dict[str, Any] = None
    ) -> int:
        """Add new knowledge to the knowledge base.

        Args:
            user_id: User ID
            title: Knowledge title
            content: Knowledge content
            para_type: Type of knowledge (concept, action, reference)
            tags: Optional tags
            metadata: Optional metadata

        Returns:
            ID of created knowledge card
        """
        pass

    @abstractmethod
    async def get_context_for_task(
        self,
        user_id: int,
        task_id: int,
        task_description: str
    ) -> KnowledgeContext:
        """Get relevant knowledge context for a specific task.

        This is the main integration point for the AI agent to access
        user knowledge when working on tasks.

        Args:
            user_id: User ID
            task_id: Task ID
            task_description: Task description for semantic search

        Returns:
            Formatted knowledge context for AI consumption
        """
        pass

    @abstractmethod
    async def get_user_knowledge_stats(
        self,
        user_id: int
    ) -> dict[str, Any]:
        """Get user's knowledge statistics.

        Args:
            user_id: User ID

        Returns:
            Statistics including total cards, cards by type, etc.
        """
        pass
