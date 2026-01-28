"""Local JSON-based memory provider implementation."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_os.core.interfaces import MemoryProvider
from agent_os.core.types import RuntimeContext


class LocalJSONProvider(MemoryProvider):
    """In-memory JSON-based memory provider with optional persistence."""

    def __init__(self, storage_path: str | None = None) -> None:
        """Initialize the memory provider.

        Args:
            storage_path: Optional path to persist memories. If None, memories are only in-memory.
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self._memories: dict[str, dict[str, Any]] = {}

        # Load existing memories if storage path is provided
        if self.storage_path and self.storage_path.exists():
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load memories from disk."""
        if not self.storage_path:
            return

        try:
            with open(self.storage_path, encoding="utf-8") as f:
                data = json.load(f)
                self._memories = data.get("memories", {})
        except (json.JSONDecodeError, FileNotFoundError):
            self._memories = {}

    def _save_to_disk(self) -> None:
        """Save memories to disk."""
        if not self.storage_path:
            return

        # Ensure parent directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "memories": self._memories,
                    "updated_at": datetime.now().isoformat(),
                },
                f,
                indent=2,
            )

    def _get_user_key(self, ctx: RuntimeContext) -> str:
        """Get the storage key for a user's memories."""
        return f"user:{ctx.user_id}"

    async def add(
        self,
        ctx: RuntimeContext,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a memory for the given user context."""
        memory_id = str(uuid.uuid4())
        user_key = self._get_user_key(ctx)

        memory_entry = {
            "id": memory_id,
            "user_id": ctx.user_id,
            "content": content,
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
            "session_id": ctx.session_id,
        }

        # Store in user-scoped memories
        if user_key not in self._memories:
            self._memories[user_key] = {}
        self._memories[user_key][memory_id] = memory_entry

        # Persist if storage path is configured
        self._save_to_disk()

        return memory_id

    async def search(
        self,
        ctx: RuntimeContext,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Search memories using simple keyword matching.

        Note: This is a simple implementation. For production, consider using
        vector embeddings for semantic search.
        """
        user_key = self._get_user_key(ctx)
        user_memories = self._memories.get(user_key, {})

        # Simple keyword matching - check if query terms appear in content
        query_terms = query.lower().split()
        results: list[tuple[str, float, dict[str, Any]]] = []

        for memory_id, memory in user_memories.items():
            content = memory.get("content", "").lower()
            metadata_str = str(memory.get("metadata", {})).lower()

            # Calculate a simple relevance score
            score = 0.0
            for term in query_terms:
                if term in content:
                    score += 1.0
                if term in metadata_str:
                    score += 0.5

            if score > 0:
                results.append((memory_id, score, memory))

        # Sort by score (descending) and limit results
        results.sort(key=lambda x: x[1], reverse=True)
        limited_results = results[:limit]

        # Return with scores
        return [
            {
                "id": memory_id,
                "score": score,
                "content": memory["content"],
                "metadata": memory.get("metadata", {}),
                "created_at": memory.get("created_at"),
            }
            for memory_id, score, memory in limited_results
        ]

    async def get(self, ctx: RuntimeContext, memory_id: str) -> dict[str, Any] | None:
        """Get a specific memory by ID."""
        user_key = self._get_user_key(ctx)
        user_memories = self._memories.get(user_key, {})
        return user_memories.get(memory_id)

    async def delete(self, ctx: RuntimeContext, memory_id: str) -> bool:
        """Delete a memory by ID."""
        user_key = self._get_user_key(ctx)
        user_memories = self._memories.get(user_key, {})

        if memory_id in user_memories:
            del user_memories[memory_id]
            self._save_to_disk()
            return True
        return False

    async def list_all(self, ctx: RuntimeContext) -> list[dict[str, Any]]:
        """List all memories for a user."""
        user_key = self._get_user_key(ctx)
        user_memories = self._memories.get(user_key, {})
        return list(user_memories.values())


__all__ = ["LocalJSONProvider"]
