"""Unit tests for Vector embedding and search functionality."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from agent_os.knowledge.embeddings import (
    EmbeddingService,
    generate_embedding_for_card,
    generate_embedding_for_inbox,
)


# =============================================================================
# Embedding Service Tests
# =============================================================================

class TestEmbeddingService:
    """Test EmbeddingService functionality."""

    def test_get_embedding_dimension(self):
        """Test getting embedding dimension."""
        dim = EmbeddingService.get_embedding_dimension()
        assert dim == 384

    @patch('agent_os.knowledge.embeddings.SentenceTransformer')
    def test_embed_text_success(self, mock_transformer_class):
        """Test successful text embedding."""
        # Mock the model
        mock_model = Mock()
        mock_transformer_class.return_value = mock_model

        # Mock the encode method to return a dummy embedding
        dummy_embedding = np.random.rand(384).astype(np.float32)
        mock_model.encode.return_value = dummy_embedding

        # Reset the cached model
        EmbeddingService._model = None

        # Test embedding
        result = EmbeddingService.embed_text("Test text")

        # Verify
        assert result is not None
        assert len(result) == 384
        assert all(isinstance(x, float) for x in result)

        # Verify model was called
        mock_model.encode.assert_called_once()

    def test_embed_text_empty(self):
        """Test embedding empty text."""
        result = EmbeddingService.embed_text("")
        assert result is None

        result = EmbeddingService.embed_text("   ")
        assert result is None

    @patch('agent_os.knowledge.embeddings.SentenceTransformer')
    def test_embed_text_error_handling(self, mock_transformer_class):
        """Test error handling in embedding."""
        # Mock to raise exception
        mock_transformer_class.side_effect = Exception("Model load error")

        # Reset cached model
        EmbeddingService._model = None

        # Test embedding
        result = EmbeddingService.embed_text("Test text")

        # Should return None on error
        assert result is None

    @patch('agent_os.knowledge.embeddings.SentenceTransformer')
    def test_embed_texts_batch(self, mock_transformer_class):
        """Test batch embedding."""
        # Mock the model
        mock_model = Mock()
        mock_transformer_class.return_value = mock_model

        # Mock encode to return multiple embeddings
        embeddings = np.random.rand(3, 384).astype(np.float32)
        mock_model.encode.return_value = embeddings

        # Reset cached model
        EmbeddingService._model = None

        # Test batch embedding
        texts = ["Text 1", "Text 2", "Text 3"]
        results = EmbeddingService.embed_texts(texts)

        # Verify
        assert len(results) == 3
        assert all(len(r) == 384 for r in results if r is not None)

    def test_compute_similarity(self):
        """Test similarity computation."""
        # Create two identical vectors
        vec1 = [1.0, 2.0, 3.0, 4.0]
        vec2 = [1.0, 2.0, 3.0, 4.0]

        similarity = EmbeddingService.compute_similarity(vec1, vec2)

        # Should be 1.0 for identical vectors
        assert abs(similarity - 1.0) < 0.001

    def test_compute_similarity_different_vectors(self):
        """Test similarity with different vectors."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = EmbeddingService.compute_similarity(vec1, vec2)

        # Should be 0.0 for orthogonal vectors
        assert abs(similarity - 0.0) < 0.001

    def test_compute_similarity_opposite_vectors(self):
        """Test similarity with opposite vectors."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [-1.0, -2.0, -3.0]

        similarity = EmbeddingService.compute_similarity(vec1, vec2)

        # Should be -1.0 for opposite vectors
        assert abs(similarity - (-1.0)) < 0.001

    def test_compute_similarity_zero_vector(self):
        """Test similarity with zero vector."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [0.0, 0.0, 0.0]

        similarity = EmbeddingService.compute_similarity(vec1, vec2)

        # Should return 0.0 for zero vector
        assert similarity == 0.0


class TestEmbeddingGeneration:
    """Test embedding generation for cards and inbox items."""

    @patch('agent_os.knowledge.embeddings.EmbeddingService.embed_text')
    def test_generate_embedding_for_card(self, mock_embed):
        """Test generating embedding for a card."""
        # Mock the embedding
        mock_embed.return_value = [0.1] * 384

        # Test
        result = generate_embedding_for_card("Test Title", "Test Content")

        # Verify
        assert result is not None
        assert len(result) == 384

        # Verify the combined text was used
        mock_embed.assert_called_once()
        call_args = mock_embed.call_args[0][0]
        assert "Test Title" in call_args
        assert "Test Content" in call_args

    @patch('agent_os.knowledge.embeddings.EmbeddingService.embed_text')
    def test_generate_embedding_for_inbox(self, mock_embed):
        """Test generating embedding for inbox item."""
        # Mock the embedding
        mock_embed.return_value = [0.2] * 384

        # Test
        result = generate_embedding_for_inbox("Inbox content here")

        # Verify
        assert result is not None
        assert len(result) == 384
        mock_embed.assert_called_once_with("Inbox content here")

    @patch('agent_os.knowledge.embeddings.EmbeddingService.embed_text')
    def test_generate_embedding_for_card_empty(self, mock_embed):
        """Test generating embedding for empty card."""
        # Mock to return None
        mock_embed.return_value = None

        # Test
        result = generate_embedding_for_card("", "")

        # Verify
        assert result is None


# =============================================================================
# Vector Search Schema Tests
# =============================================================================

class TestVectorSearchSchemas:
    """Test vector search request/response schemas."""

    def test_vector_search_request_valid(self):
        """Test valid vector search request."""
        from agent_os.knowledge.router import VectorSearchRequest

        req = VectorSearchRequest(
            query="test query",
            limit=10,
            para_type="concept"
        )
        assert req.query == "test query"
        assert req.limit == 10
        assert req.para_type == "concept"

    def test_vector_search_request_defaults(self):
        """Test default values."""
        from agent_os.knowledge.router import VectorSearchRequest

        req = VectorSearchRequest(query="test")
        assert req.limit == 10
        assert req.para_type is None

    def test_vector_search_request_query_too_short(self):
        """Test query too short."""
        from agent_os.knowledge.router import VectorSearchRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            VectorSearchRequest(query="")

    def test_vector_search_request_limit_bounds(self):
        """Test limit bounds validation."""
        from agent_os.knowledge.router import VectorSearchRequest

        # Valid range
        VectorSearchRequest(query="test", limit=1)
        VectorSearchRequest(query="test", limit=50)

    def test_vector_search_result_item(self):
        """Test search result item."""
        from agent_os.knowledge.router import VectorSearchResultItem

        result = VectorSearchResultItem(
            card_id=1,
            title="Test Card",
            content="Test content",
            para_type="concept",
            similarity=0.95
        )
        assert result.card_id == 1
        assert result.similarity == 0.95

    def test_vector_search_result_item_similarity_bounds(self):
        """Test similarity bounds validation."""
        from agent_os.knowledge.router import VectorSearchResultItem
        from pydantic import ValidationError

        # Valid range
        VectorSearchResultItem(
            card_id=1,
            title="Test",
            content="Content",
            para_type="concept",
            similarity=0.0
        )
        VectorSearchResultItem(
            card_id=1,
            title="Test",
            content="Content",
            para_type="concept",
            similarity=1.0
        )

        # Invalid: too high
        with pytest.raises(ValidationError):
            VectorSearchResultItem(
                card_id=1,
                title="Test",
                content="Content",
                para_type="concept",
                similarity=1.1
            )

        # Invalid: too low
        with pytest.raises(ValidationError):
            VectorSearchResultItem(
                card_id=1,
                title="Test",
                content="Content",
                para_type="concept",
                similarity=-0.1
            )

    def test_vector_search_response(self):
        """Test search response."""
        from agent_os.knowledge.router import VectorSearchResponse, VectorSearchResultItem

        results = [
            VectorSearchResultItem(
                card_id=1,
                title="Card 1",
                content="Content 1",
                para_type="concept",
                similarity=0.95
            )
        ]

        response = VectorSearchResponse(
            query="test query",
            results=results,
            total=1
        )
        assert response.query == "test query"
        assert response.total == 1
        assert len(response.results) == 1


# =============================================================================
# Mock Tests (without sentence-transformers)
# =============================================================================

class TestEmbeddingServiceUnit:
    """Unit tests that don't require sentence-transformers."""

    def test_embedding_dimension_constant(self):
        """Test embedding dimension is correctly set."""
        assert EmbeddingService._embedding_dim == 384

    def test_model_name_constant(self):
        """Test model name is correctly set."""
        assert "MiniLM" in EmbeddingService._model_name
        assert "L6" in EmbeddingService._model_name

    def test_singleton_model(self):
        """Test model is singleton."""
        # Get model twice
        model1 = EmbeddingService._model
        model2 = EmbeddingService._model

        # Should be the same instance
        assert model1 is model2
