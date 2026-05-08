"""Embedding Service - Generates vector embeddings for semantic search.

This module provides a simple, fast local embedding solution:
- Uses a lightweight TF-IDF + hashing approach
- No external API calls
- Fast and suitable for demo/development
- Can be replaced with proper embeddings later
"""

import logging
import math
import re
from collections import Counter
from typing import List

logger = logging.getLogger(__name__)


class SimpleEmbedding:
    """Simple embedding generator using TF-IDF-like approach.

    This is a fast, local alternative to API-based embeddings.
    For production, replace with OpenAI Embeddings or sentence-transformers.
    """

    def __init__(self, embedding_dim: int = 384):
        """Initialize embedding generator.

        Args:
            embedding_dim: Dimension of embedding vectors (default: 384, matches all-MiniLM-L6-v2)
        """
        self.embedding_dim = embedding_dim
        self.vocab = {}  # Word -> index mapping
        self.word_count = Counter()
        self.num_documents = 0

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words.

        Args:
            text: Input text

        Returns:
            List of tokens
        """
        # Simple tokenization: lowercase, alphanumeric, split
        text = text.lower()
        words = re.findall(r'\b\w+\b', text)
        return words

    def _build_vocab(self, texts: list[str]):
        """Build vocabulary from texts.

        Args:
            texts: List of texts
        """
        for text in texts:
            words = set(self._tokenize(text))
            for word in words:
                self.word_count[word] += 1

        # Use most common words for vocab
        vocab_size = 5000
        common_words = self.word_count.most_common(vocab_size)
        self.vocab = {word: idx for idx, (word, _) in enumerate(common_words)}

    def _get_tfidf_vector(self, text: str) -> list[float]:
        """Generate TF-IDF-like vector.

        Args:
            text: Input text

        Returns:
            Vector of floats
        """
        words = self._tokenize(text)
        word_freq = Counter(words)

        # Calculate TF-IDF scores
        scores = []
        for word, idx in self.vocab.items():
            tf = word_freq.get(word, 0) / len(words) if words else 0
            # Simple IDF approximation
            idf = math.log(1 + self.word_count.get(word, 1))
            scores.append(tf * idf)

        # Pad or truncate to embedding_dim
        if len(scores) < self.embedding_dim:
            scores.extend([0.0] * (self.embedding_dim - len(scores)))
        else:
            scores = scores[:self.embedding_dim]

        # Normalize
        norm = math.sqrt(sum(s * s for s in scores))
        if norm > 0:
            scores = [s / norm for s in scores]

        return scores

    def fit(self, texts: list[str]):
        """Fit the embedding model on texts.

        Args:
            texts: Training texts
        """
        self._build_vocab(texts)
        self.num_documents = len(texts)
        logger.info(f"Fitted embedding model on {self.num_documents} documents, vocab size: {len(self.vocab)}")

    def encode(self, text: str) -> list[float]:
        """Encode text to embedding vector.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        return self._get_tfidf_vector(text)

    def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode multiple texts.

        Args:
            texts: List of texts

        Returns:
            List of embedding vectors
        """
        return [self.encode(text) for text in texts]


class EmbeddingService:
    """Service for generating and managing embeddings."""

    def __init__(self, embedding_dim: int = 384):
        """Initialize embedding service.

        Args:
            embedding_dim: Dimension of embeddings
        """
        self.embedding_dim = embedding_dim
        self.model = SimpleEmbedding(embedding_dim)
        self._fitted = False

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector
        """
        if not self._fitted:
            # Lazy fit with some sample data
            sample_texts = [
                "This is a sample document about software development.",
                "Python is a popular programming language for data science.",
                "Machine learning models can process large amounts of data.",
                "Web applications use frameworks like FastAPI and Django.",
                "Databases store and retrieve information efficiently."
            ]
            self.model.fit(sample_texts)
            self._fitted = True

        return self.model.encode(text)

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts

        Returns:
            List of embedding vectors
        """
        if not self._fitted:
            # Fit on the texts themselves
            self.model.fit(texts)
            self._fitted = True

        return self.model.encode_batch(texts)

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Similarity score between -1 and 1
        """
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


# Global embedding service instance
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Get or create global embedding service.

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
