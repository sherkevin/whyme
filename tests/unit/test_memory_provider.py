"""Tests for MemoryProvider."""

from pathlib import Path

import pytest

from agent_os.core.types import RuntimeContext
from agent_os.memory import LocalJSONProvider


class TestLocalJSONProvider:
    """Test suite for LocalJSONProvider."""

    @pytest.fixture
    def runtime_context(self) -> RuntimeContext:
        """Create a runtime context for testing."""
        return RuntimeContext(
            session_id="test_session",
            user_id="test_user",
            trace_id="test_trace",
        )

    @pytest.fixture
    async def memory_provider(self, tmp_path: Path) -> LocalJSONProvider:
        """Create a memory provider with temporary storage."""
        storage_path = tmp_path / "memory.json"
        return LocalJSONProvider(str(storage_path))

    @pytest.mark.asyncio
    async def test_add_memory(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test adding a memory."""
        memory_id = await memory_provider.add(
            runtime_context,
            content="Test memory content",
            metadata={"key": "value"},
        )

        assert memory_id is not None
        assert isinstance(memory_id, str)

        # Verify memory was stored
        memories = await memory_provider.list_all(runtime_context)
        assert len(memories) == 1
        assert memories[0]["content"] == "Test memory content"
        assert memories[0]["metadata"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_add_multiple_memories(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test adding multiple memories."""
        await memory_provider.add(runtime_context, content="Memory 1")
        await memory_provider.add(runtime_context, content="Memory 2")
        await memory_provider.add(runtime_context, content="Memory 3")

        memories = await memory_provider.list_all(runtime_context)
        assert len(memories) == 3

    @pytest.mark.asyncio
    async def test_search_memories(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test searching memories."""
        await memory_provider.add(runtime_context, content="Python is a programming language")
        await memory_provider.add(runtime_context, content="JavaScript is also a programming language")
        await memory_provider.add(runtime_context, content="I like pizza")

        results = await memory_provider.search(runtime_context, query="programming", limit=10)

        assert len(results) == 2
        assert all("programming" in r["content"].lower() for r in results)

    @pytest.mark.asyncio
    async def test_search_with_limit(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test searching with a limit."""
        for i in range(10):
            await memory_provider.add(runtime_context, content=f"Memory about programming {i}")

        results = await memory_provider.search(runtime_context, query="programming", limit=5)

        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_search_returns_relevant_scores(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test that search results include relevance scores."""
        await memory_provider.add(runtime_context, content="Python programming language")
        await memory_provider.add(runtime_context, content="I like cats")

        results = await memory_provider.search(runtime_context, query="Python programming")

        assert len(results) >= 1
        assert "score" in results[0]
        assert results[0]["score"] > 0

    @pytest.mark.asyncio
    async def test_get_memory_by_id(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test retrieving a specific memory by ID."""
        memory_id = await memory_provider.add(
            runtime_context,
            content="Specific memory content",
            metadata={"tag": "test"},
        )

        memory = await memory_provider.get(runtime_context, memory_id)

        assert memory is not None
        assert memory["content"] == "Specific memory content"
        assert memory["metadata"]["tag"] == "test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_memory(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test retrieving a non-existent memory."""
        memory = await memory_provider.get(runtime_context, "nonexistent_id")
        assert memory is None

    @pytest.mark.asyncio
    async def test_delete_memory(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test deleting a memory."""
        memory_id = await memory_provider.add(runtime_context, content="To be deleted")

        # Verify it exists
        assert await memory_provider.get(runtime_context, memory_id) is not None

        # Delete it
        result = await memory_provider.delete(runtime_context, memory_id)
        assert result is True

        # Verify it's gone
        assert await memory_provider.get(runtime_context, memory_id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_memory(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test deleting a non-existent memory."""
        result = await memory_provider.delete(runtime_context, "nonexistent_id")
        assert result is False

    @pytest.mark.asyncio
    async def test_user_isolation(self, tmp_path: Path) -> None:
        """Test that memories are isolated between users."""
        provider = LocalJSONProvider(str(tmp_path / "test.json"))

        ctx1 = RuntimeContext(
            session_id="session1",
            user_id="user1",
            trace_id="trace1",
        )
        ctx2 = RuntimeContext(
            session_id="session2",
            user_id="user2",
            trace_id="trace2",
        )

        await provider.add(ctx1, content="User 1 memory")
        await provider.add(ctx2, content="User 2 memory")

        memories1 = await provider.list_all(ctx1)
        memories2 = await provider.list_all(ctx2)

        assert len(memories1) == 1
        assert len(memories2) == 1
        assert memories1[0]["content"] == "User 1 memory"
        assert memories2[0]["content"] == "User 2 memory"

    @pytest.mark.asyncio
    async def test_persistence(self, tmp_path: Path) -> None:
        """Test that memories persist across provider instances."""
        storage_path = tmp_path / "persist_test.json"
        ctx = RuntimeContext(
            session_id="session",
            user_id="user",
            trace_id="trace",
        )

        # Create first provider and add a memory
        provider1 = LocalJSONProvider(str(storage_path))
        memory_id = await provider1.add(ctx, content="Persistent memory")

        # Create second provider with same storage path
        provider2 = LocalJSONProvider(str(storage_path))

        # Verify memory is still there
        memory = await provider2.get(ctx, memory_id)
        assert memory is not None
        assert memory["content"] == "Persistent memory"

    @pytest.mark.asyncio
    async def test_in_memory_mode(self, runtime_context: RuntimeContext) -> None:
        """Test provider without storage path (in-memory only)."""
        provider = LocalJSONProvider(storage_path=None)

        await provider.add(runtime_context, content="In-memory data")
        memories = await provider.list_all(runtime_context)

        assert len(memories) == 1
        assert memories[0]["content"] == "In-memory data"

    @pytest.mark.asyncio
    async def test_search_empty_query(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test searching with an empty query."""
        await memory_provider.add(runtime_context, content="Test content")

        results = await memory_provider.search(runtime_context, query="")

        # Empty query should return no results
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_no_matches(
        self,
        memory_provider: LocalJSONProvider,
        runtime_context: RuntimeContext,
    ) -> None:
        """Test searching when there are no matches."""
        await memory_provider.add(runtime_context, content="Python programming")

        results = await memory_provider.search(runtime_context, query="quantum physics")

        assert len(results) == 0
