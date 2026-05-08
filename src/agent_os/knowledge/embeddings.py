"""Vector embedding service for knowledge cards."""

import logging
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


# =============================================================================
# Embedding Service
# =============================================================================

class EmbeddingService:
    """Service for generating vector embeddings using sentence-transformers."""

    _model: SentenceTransformer | None = None
    _model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    _embedding_dim: int = 384

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """Get or initialize the sentence-transformer model.

        Returns:
            SentenceTransformer model instance
        """
        if cls._model is None:
            logger.info(f"Loading embedding model: {cls._model_name}")
            cls._model = SentenceTransformer(cls._model_name)
            logger.info(f"Model loaded successfully. Embedding dimension: {cls._embedding_dim}")
        return cls._model

    @classmethod
    def embed_text(cls, text: str) -> list[float] | None:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of float values representing the embedding vector,
            or None if embedding fails
        """
        if not text or not text.strip():
            logger.warning("Cannot embed empty text")
            return None

        try:
            model = cls.get_model()
            embedding = model.encode(text, convert_to_numpy=True)

            # Convert to list and ensure it's a Python list
            embedding_list = embedding.tolist()

            # Validate embedding dimension
            if len(embedding_list) != cls._embedding_dim:
                logger.error(
                    f"Embedding dimension mismatch: "
                    f"expected {cls._embedding_dim}, got {len(embedding_list)}"
                )
                return None

            return embedding_list

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    @classmethod
    def embed_texts(cls, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors (or None for failed embeddings)
        """
        if not texts:
            return []

        try:
            model = cls.get_model()
            embeddings = model.encode(texts, convert_to_numpy=True)

            results = []
            for i, embedding in enumerate(embeddings):
                embedding_list = embedding.tolist()
                if len(embedding_list) == cls._embedding_dim:
                    results.append(embedding_list)
                else:
                    logger.warning(f"Embedding {i} has invalid dimension")
                    results.append(None)

            return results

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return [None] * len(texts)

    @classmethod
    def compute_similarity(cls, embedding1: list[float], embedding2: list[float]) -> float:
        """Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score (-1 to 1, typically 0 to 1 for normalized vectors)
        """
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            # Compute cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            # Clamp to [-1, 1]
            return float(max(-1.0, min(1.0, similarity)))

        except Exception as e:
            logger.error(f"Error computing similarity: {e}")
            return 0.0

    @classmethod
    def get_embedding_dimension(cls) -> int:
        """Get the embedding dimension.

        Returns:
            Embedding vector dimension
        """
        return cls._embedding_dim


# =============================================================================
# Utility Functions
# =============================================================================

def generate_embedding_for_card(title: str, content: str) -> list[float] | None:
    """Generate embedding for a card by combining title and content.

    Args:
        title: Card title
        content: Card content

    Returns:
        Embedding vector or None if generation fails
    """
    # Combine title and content with more weight on title
    combined_text = f"{title}. {content}"
    return EmbeddingService.embed_text(combined_text)


def generate_embedding_for_inbox(content: str) -> list[float] | None:
    """Generate embedding for an inbox item.

    Args:
        content: Inbox item content

    Returns:
        Embedding vector or None if generation fails
    """
    return EmbeddingService.embed_text(content)
