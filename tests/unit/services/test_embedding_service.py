"""Unit tests for Stage 4 Embedding Service."""

import pytest
import asyncio
from agent_os.search_engine.embedding_service import SimpleEmbedding, EmbeddingService
from agent_os.search_engine.models import SearchIndex


@pytest.mark.asyncio
class TestSimpleEmbedding:
    """Test SimpleEmbedding functionality."""

    async def test_tokenize(self, db_session):
        """Test text tokenization."""
        embedder = SimpleEmbedding()

        text = "Hello, World! This is a test."
        tokens = embedder._tokenize(text)

        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens
        assert len(tokens) > 0
        print(f"✅ Tokenization: {len(tokens)} tokens")

    async def test_build_vocab(self, db_session):
        """Test vocabulary building."""
        embedder = SimpleEmbedding()

        texts = [
            "Python is great",
            "Python for data science",
            "Machine learning with Python"
        ]

        embedder._build_vocab(texts)

        assert len(embedder.vocab) > 0
        assert "python" in embedder.vocab
        assert "data" in embedder.vocab
        print(f"✅ Vocabulary: {len(embedder.vocab)} words")

    async def test_get_tfidf_vector(self, db_session):
        """Test TF-IDF vector generation."""
        embedder = SimpleEmbedding()

        # Build vocab first
        embedder._build_vocab([
            "Python is great",
            "Python for data science",
            "Machine learning with Python"
        ])

        vector = embedder._get_tfidf_vector("Python programming")

        assert len(vector) == embedder.embedding_dim
        assert all(isinstance(v, float) for v in vector)
        assert abs(sum(v * v for v in vector) - 1.0) < 0.01  # Normalized
        print(f"✅ TF-IDF vector: {len(vector)} dimensions, normalized")

    async def test_encode(self, db_session):
        """Test text encoding."""
        embedder = SimpleEmbedding()

        # Fit on some texts
        texts = [
            "This is about programming",
            "Python is a programming language",
            "Web development is popular"
        ]
        embedder.fit(texts)

        # Encode new text
        vector = embedder.encode("Python programming")

        assert len(vector) == embedder.embedding_dim
        assert len(vector) == 384  # Default dimension
        print(f"✅ Encode: generated {len(vector)}-d vector")

    async def test_encode_batch(self, db_session):
        """Test batch encoding."""
        embedder = SimpleEmbedding()

        texts = [
            "First document about cats",
            "Second document about dogs",
            "Third document about birds"
        ]
        embedder.fit(texts)

        vectors = embedder.encode_batch(["Cats are cute", "Dogs are loyal"])

        assert len(vectors) == 2
        assert all(len(v) == embedder.embedding_dim for v in vectors)
        print(f"✅ Batch encode: {len(vectors)} vectors")


@pytest.mark.asyncio
class TestEmbeddingService:
    """Test EmbeddingService functionality."""

    async def test_generate_embedding(self, db_session):
        """Test embedding generation."""
        service = EmbeddingService()

        vector = await service.generate_embedding("This is a test document")

        assert len(vector) == service.embedding_dim
        assert len(vector) == 384
        assert all(isinstance(v, float) for v in vector)
        print(f"✅ Generated embedding: {len(vector)}-d vector")

    async def test_generate_embeddings_batch(self, db_session):
        """Test batch embedding generation."""
        service = EmbeddingService()

        texts = [
            "Document about machine learning",
            "Document about web development",
            "Document about data science"
        ]

        vectors = await service.generate_embeddings_batch(texts)

        assert len(vectors) == 3
        assert all(len(v) == 384 for v in vectors)
        print(f"✅ Batch generation: {len(vectors)} embeddings")

    async def test_cosine_similarity(self, db_session):
        """Test cosine similarity calculation."""
        service = EmbeddingService()

        # Two similar vectors
        vec1 = [1.0, 0.0, 0.0, 1.0]
        vec2 = [1.0, 0.0, 0.0, 0.5]

        similarity = service.cosine_similarity(vec1, vec2)

        assert 0 < similarity <= 1.0
        print(f"✅ Cosine similarity: {similarity:.4f}")

    async def test_cosine_similarity_identical(self, db_session):
        """Test cosine similarity of identical vectors."""
        service = EmbeddingService()

        vec = [0.5, 0.5, 0.5, 0.5]
        similarity = service.cosine_similarity(vec, vec)

        assert abs(similarity - 1.0) < 0.001  # Should be 1.0
        print(f"✅ Identical vectors: similarity = {similarity:.4f}")

    async def test_cosine_similarity_orthogonal(self, db_session):
        """Test cosine similarity of orthogonal vectors."""
        service = EmbeddingService()

        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = service.cosine_similarity(vec1, vec2)

        assert abs(similarity) < 0.001  # Should be 0.0
        print(f"✅ Orthogonal vectors: similarity = {similarity:.4f}")

    async def test_embedding_persistence(self, db_session):
        """Test that embeddings are consistent."""
        service = EmbeddingService()

        text = "Consistent test document"

        # Generate twice
        vec1 = await service.generate_embedding(text)
        vec2 = await service.generate_embedding(text)

        # Should be identical (deterministic)
        assert len(vec1) == len(vec2)
        for i in range(len(vec1)):
            assert abs(vec1[i] - vec2[i]) < 0.001

        print(f"✅ Embedding consistency: vectors are identical")


@pytest.mark.asyncio
class TestEmbeddingIntegration:
    """Integration tests for embedding with search."""

    async def test_search_with_embeddings(self, db_session):
        """Test that embeddings work with search."""
        from agent_os.search_engine.search_service import SearchService
        from agent_os.search_engine.search_engine import SearchEngine, SearchQuery
        import uuid

        # Enable auto-embedding
        search_service = SearchService(db_session, auto_embed=True)

        # Create some indexed items
        item1_id = uuid.uuid4()
        await search_service.index_item(
            item_type="card",
            item_id=str(item1_id),
            title="Python Programming Guide",
            content="Learn Python programming from scratch"
        )

        item2_id = uuid.uuid4()
        await search_service.index_item(
            item_type="card",
            item_id=str(item2_id),
            title="JavaScript Tutorial",
            content="Learn JavaScript web development"
        )

        # Verify embeddings were created
        from sqlalchemy import select
        stmt = select(SearchIndex).where(SearchIndex.item_id == item1_id)
        result = await db_session.execute(stmt)
        index1 = result.scalar_one_or_none()

        assert index1 is not None
        assert index1.embedding is not None
        assert len(index1.embedding) > 0
        print(f"✅ Embedding created: {len(index1.embedding)}-d vector")

        # Search with vector search enabled
        engine = SearchEngine(db_session, enable_vector_search=True)
        query = SearchQuery(query="Python")
        result = await engine.search(query)

        assert result.total >= 1
        print(f"✅ Search with embeddings: {result.total} results")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
