"""RAG (Retrieval-Augmented Generation) interface layer.

This module provides an abstraction layer between the knowledge management
system and the AI agent, allowing them to evolve independently.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class SearchResult(BaseModel):
    """Single search result from knowledge base."""

    id: int
    title: str
    content: str
    para_type: str
    similarity: float
    metadata: Dict[str, Any] = {}


class KnowledgeContext(BaseModel):
    """Aggregated knowledge context for AI agent."""

    query: str
    results: List[SearchResult]
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
        para_type: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[SearchResult]:
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
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
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
    ) -> Dict[str, Any]:
        """Get user's knowledge statistics.

        Args:
            user_id: User ID

        Returns:
            Statistics including total cards, cards by type, etc.
        """
        pass


class MockRAGProvider(RAGProvider):
    """Mock RAG provider for testing without database.

    This allows the system to work even when the database layer is not ready.
    """

    async def search_knowledge(
        self,
        user_id: int,
        query: str,
        limit: int = 5,
        para_type: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """Mock search - returns empty results."""
        return []

    async def add_knowledge(
        self,
        user_id: int,
        title: str,
        content: str,
        para_type: str,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> int:
        """Mock add - returns fake ID."""
        return -1

    async def get_context_for_task(
        self,
        user_id: int,
        task_id: int,
        task_description: str
    ) -> KnowledgeContext:
        """Mock context - returns empty context."""
        return KnowledgeContext(
            query=task_description,
            results=[],
            formatted_context="# No knowledge available yet.\n",
            total_cards=0,
            user_id=user_id
        )

    async def get_user_knowledge_stats(
        self,
        user_id: int
    ) -> Dict[str, Any]:
        """Mock stats - returns empty stats."""
        return {
            "total_cards": 0,
            "by_type": {},
            "recently_added": 0
        }
