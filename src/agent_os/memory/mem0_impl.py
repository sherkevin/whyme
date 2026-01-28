"""Mem0-based memory provider with vector embeddings.

This implementation uses sentence-transformers for embeddings
and FAISS for vector similarity search.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from agent_os.core.interfaces import MemoryProvider
from agent_os.core.types import RuntimeContext


class Mem0Provider(MemoryProvider):
    """Memory provider using vector embeddings for semantic search.

    This implementation:
    - Uses sentence-transformers for embeddings
    - Uses FAISS for efficient vector similarity search
    - Stores memories in memory (persisted to disk optionally)
    - Provides semantic search capabilities
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        storage_path: str | None = None,
        embedding_dim: int = 384,
    ) -> None:
        """Initialize the Mem0 provider.

        Args:
            model_name: Name of the sentence-transformers model
            storage_path: Optional path to persist memories and index
            embedding_dim: Dimension of embeddings (default for MiniLM-L6)
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.embedding_dim = embedding_dim
        self._model = None
        self._index = None
        self._memories: list[dict[str, Any]] = []

        # Load existing data if storage path is provided
        if self.storage_path and self.storage_path.exists():
            self._load_from_disk()

    def _get_model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._model_name or "all-MiniLM-L6-v2")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for Mem0Provider. "
                    "Install it with: pip install sentence-transformers"
                )
        return self._model

    def _get_index(self):
        """Lazy-load or create the FAISS index."""
        import faiss

        if self._index is None:
            self._index = faiss.IndexFlatL2(self.embedding_dim)

            # Load existing vectors if available
            if self.storage_path:
                index_file = self.storage_path / "index.faiss"
                if index_file.exists():
                    self._index = faiss.read_index(str(index_file))

        return self._index

    def _get_embedding(self, text: str) -> np.ndarray:
        """Generate embedding for text."""
        model = self._get_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.astype("float32")

    def _load_from_disk(self) -> None:
        """Load memories and index from disk."""
        if not self.storage_path:
            return

        try:
            import json

            # Load memories
            memories_file = self.storage_path / "memories.json"
            if memories_file.exists():
                with open(memories_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self._memories = data.get("memories", [])

            # Load index
            index_file = self.storage_path / "index.faiss"
            if index_file.exists():
                import faiss
                self._index = faiss.read_index(str(index_file))
        except Exception:
            # If loading fails, start fresh
            self._memories = []
            self._index = None

    def _save_to_disk(self) -> None:
        """Save memories and index to disk."""
        if not self.storage_path:
            return

        # Ensure directory exists
        self.storage_path.mkdir(parents=True, exist_ok=True)

        try:
            import json

            # Save memories
            memories_file = self.storage_path / "memories.json"
            with open(memories_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "memories": self._memories,
                        "updated_at": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                )

            # Save index
            if self._index is not None:
                index_file = self.storage_path / "index.faiss"
                import faiss
                faiss.write_index(self._index, str(index_file))
        except Exception as e:
            print(f"Warning: Failed to save to disk: {e}")

    def _get_user_key(self, ctx: RuntimeContext) -> str:
        """Get the storage key for a user's memories."""
        return f"user:{ctx.user_id}"

    async def add(
        self,
        ctx: RuntimeContext,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a memory with vector embedding."""
        memory_id = str(uuid.uuid4())

        # Generate embedding
        embedding = self._get_embedding(content)

        # Create memory entry
        memory_entry = {
            "id": memory_id,
            "user_id": ctx.user_id,
            "user_key": self._get_user_key(ctx),
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "session_id": ctx.session_id,
            "embedding_index": len(self._memories),  # Index in FAISS
        }

        # Add to memories list
        self._memories.append(memory_entry)

        # Add to FAISS index
        index = self._get_index()
        index.add(embedding.reshape(1, -1))

        # Persist if storage path is configured
        self._save_to_disk()

        return memory_id

    async def search(
        self,
        ctx: RuntimeContext,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search memories using vector similarity."""
        if not self._memories:
            return []

        # Generate query embedding
        query_embedding = self._get_embedding(query)

        # Search in FAISS index
        index = self._get_index()
        distances, indices = index.search(query_embedding.reshape(1, -1), min(limit, len(self._memories)))

        # Filter by user and format results
        user_key = self._get_user_key(ctx)
        results = []

        for score, idx in zip(distances[0], indices[0]):
            if idx >= 0 and idx < len(self._memories):
                memory = self._memories[idx]

                # Only return memories for this user
                if memory.get("user_key") == user_key:
                    # Convert L2 distance to similarity score (0-1)
                    similarity = float(1 / (1 + score))

                    results.append(
                        {
                            "id": memory["id"],
                            "score": similarity,
                            "content": memory["content"],
                            "metadata": memory.get("metadata", {}),
                            "created_at": memory.get("created_at"),
                        }
                    )

        return results

    async def get(self, ctx: RuntimeContext, memory_id: str) -> dict[str, Any] | None:
        """Get a specific memory by ID."""
        user_key = self._get_user_key(ctx)
        for memory in self._memories:
            if memory["id"] == memory_id and memory.get("user_key") == user_key:
                return memory
        return None

    async def delete(self, ctx: RuntimeContext, memory_id: str) -> bool:
        """Delete a memory by ID.

        This removes the memory from both the list and the FAISS index.
        The index is rebuilt to maintain consistency.
        """
        user_key = self._get_user_key(ctx)

        # Find the memory
        memory_to_delete = None
        for i, memory in enumerate(self._memories):
            if memory["id"] == memory_id and memory.get("user_key") == user_key:
                memory_to_delete = (i, memory)
                break

        if memory_to_delete is None:
            return False

        # Remove from list
        index, memory = memory_to_delete
        self._memories.pop(index)

        # Rebuild FAISS index
        await self._rebuild_index()

        # Persist changes
        self._save_to_disk()
        return True

    async def _rebuild_index(self) -> None:
        """Rebuild the FAISS index from current memories.

        This should be called after deleting memories to maintain
        index consistency.
        """
        import faiss

        # Create new index
        self._index = faiss.IndexFlatL2(self.embedding_dim)

        # Re-add all non-deleted memories
        for memory in self._memories:
            if not memory.get("deleted", False):
                # Regenerate embedding
                content = memory["content"]
                embedding = self._get_embedding(content)
                self._index.add(embedding.reshape(1, -1))

        # Save the rebuilt index
        if self.storage_path:
            index_file = self.storage_path / "index.faiss"
            faiss.write_index(self._index, str(index_file))

    async def list_all(self, ctx: RuntimeContext) -> list[dict[str, Any]]:
        """List all non-deleted memories for a user."""
        user_key = self._get_user_key(ctx)
        return [
            mem for mem in self._memories
            if mem.get("user_key") == user_key and not mem.get("deleted", False)
        ]

    async def cleanup_deleted(self) -> int:
        """Remove all deleted memories and rebuild index.

        Returns:
            Number of memories cleaned up.
        """
        # Count deleted memories
        deleted_count = sum(1 for mem in self._memories if mem.get("deleted", False))

        # Filter out deleted memories
        self._memories = [mem for mem in self._memories if not mem.get("deleted", False)]

        # Rebuild index
        if deleted_count > 0:
            await self._rebuild_index()
            self._save_to_disk()

        return deleted_count

    async def optimize_index(self) -> dict[str, Any]:
        """Optimize the FAISS index for better performance.

        Returns:
            Dictionary with optimization stats.
        """
        stats = {
            "total_memories": len(self._memories),
            "index_size": 0,
            "optimized": False
        }

        if self._index is not None:
            # Get index size
            stats["index_size"] = self._index.ntotal

            # If index is much larger than actual memories, rebuild it
            if stats["index_size"] > stats["total_memories"] * 1.5:
                await self._rebuild_index()
                stats["optimized"] = True
                stats["index_size"] = self._index.ntotal

        return stats


__all__ = ["Mem0Provider"]
