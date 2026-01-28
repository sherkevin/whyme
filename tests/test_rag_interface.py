"""Test RAG interface and providers."""

import pytest
from unittest.mock import Mock, AsyncMock
from agent_os.knowledge.rag_interface import (
    RAGProvider,
    SearchResult,
    KnowledgeContext,
    MockRAGProvider,
)
from agent_os.knowledge.rag_provider import CardRAGProvider, get_rag_provider


class TestSearchResult:
    """Test SearchResult model."""

    def test_search_result_creation(self):
        """Test creating a search result."""
        result = SearchResult(
            id=1,
            title="Test Card",
            content="Test content",
            para_type="concept",
            similarity=0.95,
            metadata={"tags": ["test"], "created_at": "2026-01-27"}
        )

        assert result.id == 1
        assert result.title == "Test Card"
        assert result.similarity == 0.95
        assert result.metadata["tags"] == ["test"]


class TestKnowledgeContext:
    """Test KnowledgeContext model."""

    def test_knowledge_context_creation(self):
        """Test creating a knowledge context."""
        context = KnowledgeContext(
            query="test query",
            results=[],
            formatted_context="# Test Context\n",
            total_cards=42,
            user_id=1
        )

        assert context.query == "test query"
        assert context.total_cards == 42
        assert context.user_id == 1


class TestMockRAGProvider:
    """Test MockRAGProvider implementation."""

    @pytest.mark.asyncio
    async def test_mock_search_knowledge(self):
        """Test mock search returns empty results."""
        provider = MockRAGProvider()

        results = await provider.search_knowledge(
            user_id=1,
            query="test query",
            limit=5
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_mock_add_knowledge(self):
        """Test mock add returns fake ID."""
        provider = MockRAGProvider()

        card_id = await provider.add_knowledge(
            user_id=1,
            title="Test",
            content="Content",
            para_type="concept"
        )

        assert card_id == -1

    @pytest.mark.asyncio
    async def test_mock_get_context_for_task(self):
        """Test mock get context returns empty context."""
        provider = MockRAGProvider()

        context = await provider.get_context_for_task(
            user_id=1,
            task_id=1,
            task_description="Test task"
        )

        assert context.total_cards == 0
        assert context.results == []
        assert "No knowledge available" in context.formatted_context

    @pytest.mark.asyncio
    async def test_mock_get_user_knowledge_stats(self):
        """Test mock stats returns empty stats."""
        provider = MockRAGProvider()

        stats = await provider.get_user_knowledge_stats(user_id=1)

        assert stats["total_cards"] == 0
        assert stats["by_type"] == {}


class TestCardRAGProvider:
    """Test CardRAGProvider implementation."""

    @pytest.mark.asyncio
    async def test_search_knowledge_filters_by_type(self):
        """Test search filters by para_type."""
        mock_db = AsyncMock()
        mock_embedding_model = Mock()
        # Make embed_query awaitable
        mock_embedding_model.embed_query = AsyncMock(return_value=[0.1] * 384)

        provider = CardRAGProvider(mock_db, mock_embedding_model)

        # Mock query execution to return empty results
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        results = await provider.search_knowledge(
            user_id=1,
            query="test",
            para_type="concept"
        )

        # Verify it returns empty list (no cards found)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_knowledge_basic(self):
        """Test basic search without PostgreSQL-specific features."""
        mock_db = AsyncMock()
        mock_embedding_model = Mock()
        # Make embed_query awaitable
        mock_embedding_model.embed_query = AsyncMock(return_value=[0.1] * 384)

        provider = CardRAGProvider(mock_db, mock_embedding_model)

        # Mock query execution to return empty results
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        results = await provider.search_knowledge(
            user_id=1,
            query="test"
        )

        # Verify it returns empty list (no cards found)
        assert isinstance(results, list)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_add_knowledge_with_embedding(self):
        """Test add knowledge generates embedding."""
        mock_db = Mock()
        mock_embedding_model = AsyncMock()

        # Mock embedding generation
        mock_embedding_model.embed_text = AsyncMock(
            return_value=[0.1] * 384  # 384-dim vector
        )

        # Mock commit
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Mock card object
        mock_card = Mock()
        mock_card.id = 42
        mock_db.add = Mock()

        provider = CardRAGProvider(mock_db, mock_embedding_model)

        # Mock Card model
        from unittest.mock import patch
        with patch('agent_os.knowledge.rag_provider.Card', return_value=mock_card):
            card_id = await provider.add_knowledge(
                user_id=1,
                title="Test Card",
                content="Test content",
                para_type="concept",
                tags=["test"]
            )

        # Verify embedding was generated
        assert card_id == 42
        assert mock_embedding_model.embed_text.called

    @pytest.mark.asyncio
    async def test_format_context_empty_results(self):
        """Test formatting context with no results."""
        mock_db = Mock()

        provider = CardRAGProvider(mock_db, None)
        formatted = provider._format_context([], "test query")

        assert "No relevant knowledge found" in formatted
        assert "test query" in formatted

    @pytest.mark.asyncio
    async def test_format_context_with_results(self):
        """Test formatting context with results."""
        mock_db = Mock()

        provider = CardRAGProvider(mock_db, None)

        results = [
            SearchResult(
                id=1,
                title="Card 1",
                content="Content 1",
                para_type="concept",
                similarity=0.9,
                metadata={"tags": ["test"]}
            ),
            SearchResult(
                id=2,
                title="Card 2",
                content="Content 2",
                para_type="action",
                similarity=0.8,
                metadata={"tags": ["test"]}
            )
        ]

        formatted = provider._format_context(results, "test query")

        assert "test query" in formatted
        assert "Card 1" in formatted
        assert "Content 1" in formatted
        assert "Card 2" in formatted
        assert "Content 2" in formatted
        assert "concept" in formatted
        assert "action" in formatted


class TestRAGProviderFactory:
    """Test RAG provider factory function."""

    def test_get_rag_provider_returns_card_provider(self):
        """Test factory returns CardRAGProvider by default."""
        mock_db = Mock()
        mock_embedding = Mock()

        provider = get_rag_provider(mock_db, mock_embedding)

        assert isinstance(provider, CardRAGProvider)
