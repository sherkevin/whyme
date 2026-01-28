"""Tests for DiffService."""

from __future__ import annotations

import asyncio

import pytest

from agent_os.server.diff_service import DiffService


class TestDiffService:
    """Test suite for DiffService."""

    @pytest.mark.asyncio
    async def test_generate_unified_diff(self) -> None:
        """Test unified diff generation."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        service = DiffService("test-session", queue, loop)

        original = "line1\nline2\nline3\n"
        new = "line1\nline2 modified\nline3\nline4\n"

        diff = service._generate_unified_diff("test.txt", original, new)

        assert "@@" in diff
        assert "-line2" in diff
        assert "+line2 modified" in diff
        assert "+line4" in diff

    @pytest.mark.asyncio
    async def test_send_confirm_diff_event(self) -> None:
        """Test that confirm_diff event is sent correctly."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        service = DiffService("test-session", queue, loop)

        # This will be a fire-and-forget call (we don't wait for response)
        task = asyncio.create_task(
            service.propose_change("test.py", "old", "new", "Test change")
        )

        # Wait for the event to be queued
        event = await asyncio.wait_for(queue.get(), timeout=1.0)

        assert event["type"] == "event"
        assert event["payload"]["action"] == "confirm_diff"
        assert event["payload"]["data"]["file"] == "test.py"
        assert event["payload"]["data"]["description"] == "Test change"
        assert "diff_content" in event["payload"]["data"]

        # Clean up the task
        task.cancel()

    @pytest.mark.asyncio
    async def test_diff_approval(self) -> None:
        """Test diff approval flow."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        service = DiffService("test-session", queue, loop)

        # Start proposing change (background task)
        task = asyncio.create_task(
            service.propose_change("test.py", "old content", "new content")
        )

        # Wait for event
        await asyncio.wait_for(queue.get(), timeout=1.0)

        # Simulate user approval
        diff_id = "test-session:test.py"
        service.handle_user_response("approve")

        # Wait for proposal to complete
        try:
            result = await asyncio.wait_for(task, timeout=1.0)
            assert result is True  # Approved
        except asyncio.CancelledError:
            pytest.fail("Task was cancelled unexpectedly")

    @pytest.mark.asyncio
    async def test_diff_rejection(self) -> None:
        """Test diff rejection flow."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        service = DiffService("test-session", queue, loop)

        # Start proposing change
        task = asyncio.create_task(
            service.propose_change("test.py", "old content", "new content")
        )

        # Wait for event
        await asyncio.wait_for(queue.get(), timeout=1.0)

        # Simulate user rejection
        diff_id = "test-session:test.py"
        service.handle_user_response("reject")

        # Wait for proposal to complete
        result = await asyncio.wait_for(task, timeout=1.0)
        assert result is False  # Rejected

    @pytest.mark.asyncio
    async def test_diff_timeout(self) -> None:
        """Test that diff proposal times out."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        service = DiffService("test-session", queue, loop)

        # Start proposing change with short timeout
        # We'll override the timeout for testing
        original_wait = service._wait_for_response

        async def short_wait(diff_id: str, timeout: float = 300.0) -> str:
            return await original_wait(diff_id, timeout=0.1)

        service._wait_for_response = short_wait

        task = asyncio.create_task(
            service.propose_change("test.py", "old content", "new content")
        )

        # Wait for event
        await asyncio.wait_for(queue.get(), timeout=1.0)

        # Don't respond - should timeout and return False
        result = await asyncio.wait_for(task, timeout=1.0)
        assert result is False  # Timeout = rejection

    @pytest.mark.asyncio
    async def test_empty_diff(self) -> None:
        """Test handling of empty diffs (no changes)."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        service = DiffService("test-session", queue, loop)

        same_content = "line1\nline2\nline3\n"
        diff = service._generate_unified_diff("test.txt", same_content, same_content)

        # Empty or minimal diff
        assert len(diff) == 0 or "test.txt" in diff

    @pytest.mark.asyncio
    async def test_new_file_diff(self) -> None:
        """Test diff for a new file (original is empty)."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        service = DiffService("test-session", queue, loop)

        original = ""
        new = "line1\nline2\nline3\n"

        diff = service._generate_unified_diff("new_file.py", original, new)

        assert "+line1" in diff
        assert "+line2" in diff
        assert "+line3" in diff

    @pytest.mark.asyncio
    async def test_delete_file_diff(self) -> None:
        """Test diff for deleting a file (new is empty)."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        service = DiffService("test-session", queue, loop)

        original = "line1\nline2\nline3\n"
        new = ""

        diff = service._generate_unified_diff("old_file.py", original, new)

        assert "-line1" in diff
        assert "-line2" in diff
        assert "-line3" in diff
