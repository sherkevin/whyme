"""Diff service for generating and managing code changes with confirmation.

This module provides functionality to:
1. Generate diffs between original and modified file content
2. Send diff confirmation events to WebSocket clients
3. Handle user responses (approve/reject)
4. Apply approved changes to files
"""

from __future__ import annotations

import asyncio
import difflib
from typing import Any, Optional

from agent_os.core.types import RuntimeContext


class DiffService:
    """Service for managing code diff confirmation flow."""

    def __init__(self, session_id: str, output_queue: asyncio.Queue, loop: asyncio.AbstractEventLoop) -> None:
        """Initialize the diff service.

        Args:
            session_id: The session ID for this service
            output_queue: Queue for sending WebSocket events
            loop: The asyncio event loop
        """
        self.session_id = session_id
        self._output_queue = output_queue
        self._loop = loop
        self._pending_diffs: dict[str, dict[str, Any]] = {}

    async def propose_change(
        self,
        file_path: str,
        original_content: str,
        new_content: str,
        description: str = "",
    ) -> bool:
        """Propose a file change and wait for user confirmation.

        Args:
            file_path: Path to the file being modified
            original_content: Original file content
            new_content: New file content to apply
            description: Description of the change

        Returns:
            True if user approved, False if rejected
        """
        # Generate diff
        diff_content = self._generate_unified_diff(
            file_path,
            original_content,
            new_content
        )

        # Create diff ID
        diff_id = f"{self.session_id}:{file_path}"

        # Store pending diff
        self._pending_diffs[diff_id] = {
            "file_path": file_path,
            "original_content": original_content,
            "new_content": new_content,
            "diff_content": diff_content,
            "description": description,
        }

        # Send confirmation event
        await self._send_event({
            "type": "event",
            "payload": {
                "action": "confirm_diff",
                "status": "waiting_for_user",
                "data": {
                    "file": file_path,
                    "diff_content": diff_content,
                    "description": description,
                    "diff_id": diff_id,
                }
            }
        })

        # Wait for user response (timeout after 5 minutes)
        try:
            response = await self._wait_for_response(diff_id, timeout=300)
            return response == "approve"
        except TimeoutError:
            # Timeout means reject
            return False

    async def approve_diff(self, diff_id: str) -> str:
        """Approve a pending diff and return the new content.

        Args:
            diff_id: ID of the diff to approve

        Returns:
            The new content to apply

        Raises:
            KeyError: If diff_id not found
        """
        if diff_id not in self._pending_diffs:
            raise KeyError(f"Diff {diff_id} not found")

        diff_data = self._pending_diffs[diff_id]
        new_content = diff_data["new_content"]

        # Clean up
        del self._pending_diffs[diff_id]

        return new_content

    async def reject_diff(self, diff_id: str) -> None:
        """Reject a pending diff.

        Args:
            diff_id: ID of the diff to reject

        Raises:
            KeyError: If diff_id not found
        """
        if diff_id not in self._pending_diffs:
            raise KeyError(f"Diff {diff_id} not found")

        # Clean up
        del self._pending_diffs[diff_id]

    def handle_user_response(self, response: str, diff_id: str | None = None) -> None:
        """Handle user response from WebSocket.

        Args:
            response: User response ("approve" or "reject")
            diff_id: Optional diff ID (if provided in user message)
        """
        # Find the relevant diff
        if diff_id and diff_id in self._pending_diffs:
            target_diff_id = diff_id
        elif len(self._pending_diffs) == 1:
            # Only one pending diff, use that
            target_diff_id = list(self._pending_diffs.keys())[0]
        else:
            # Multiple diffs or none, need explicit ID
            return

        # Set the response
        self._pending_diffs[target_diff_id]["user_response"] = response

    def _generate_unified_diff(
        self,
        file_path: str,
        original_content: str,
        new_content: str,
        context_lines: int = 3,
    ) -> str:
        """Generate unified diff between two content strings.

        Args:
            file_path: Path for display in diff header
            original_content: Original content
            new_content: New content
            context_lines: Number of context lines to show

        Returns:
            Unified diff string
        """
        original_lines = original_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
            n=context_lines,
        )

        return "".join(diff)

    async def _send_event(self, event: dict[str, Any]) -> None:
        """Send an event to the output queue."""
        try:
            await self._output_queue.put(event)
        except Exception as e:
            print(f"[DiffService] Failed to send event: {e}")

    async def _wait_for_response(self, diff_id: str, timeout: float = 300.0) -> str:
        """Wait for user response to a diff proposal.

        Args:
            diff_id: ID of the diff to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            "approve" or "reject"

        Raises:
            asyncio.TimeoutError: If timeout is reached
        """
        # Poll for response
        start_time = asyncio.get_event_loop().time()

        while True:
            if diff_id in self._pending_diffs:
                diff_data = self._pending_diffs[diff_id]
                if "user_response" in diff_data:
                    return diff_data["user_response"]

            # Check timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Timeout waiting for response to diff {diff_id}")

            # Wait a bit before polling again
            await asyncio.sleep(0.1)


class DiffAwareAiderAdapter:
    """Aider adapter with diff confirmation support.

    This adapter extends the basic AiderAdapter to provide
    interactive diff confirmation before applying changes.
    """

    def __init__(
        self,
        session_id: str,
        sandbox: Any,
        output_queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Initialize the diff-aware adapter.

        Args:
            session_id: Session ID
            sandbox: Sandbox instance for file operations
            output_queue: Queue for WebSocket events
            loop: Asyncio event loop
        """
        from agent_os.capabilities.coding.aider_adapter import AiderAdapter

        self._base_adapter = AiderAdapter()
        self._diff_service = DiffService(session_id, output_queue, loop)
        self._sandbox = sandbox

    async def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions from base adapter."""
        return await self._base_adapter.get_tool_definitions()

    async def execute_tool(
        self,
        ctx: RuntimeContext,
        name: str,
        args: dict[str, Any],
    ) -> str:
        """Execute a tool with diff confirmation for file writes.

        For write_file operations, this will:
        1. Get original file content
        2. Generate diff
        3. Send confirmation request
        4. Wait for user response
        5. Apply or reject based on response
        """
        from agent_os.server.app import _session_manager

        if not ctx.session_id:
            raise ValueError("Session ID required")

        sandbox = await _session_manager.get_or_create_sandbox(ctx.session_id)

        # For write operations with diff confirmation
        if name == "write_file" and "path" in args and "content" in args:
            file_path = args["path"]
            new_content = args["content"]

            # Get original content
            try:
                original_content = await sandbox.read_file(file_path)
            except Exception:
                # File doesn't exist yet
                original_content = ""

            # Skip confirmation if no change
            if original_content == new_content:
                return f"File {file_path} is already up to date."

            # Propose change
            approved = await self._diff_service.propose_change(
                file_path=file_path,
                original_content=original_content,
                new_content=new_content,
                description=f"Update {file_path}",
            )

            if approved:
                # Apply the change
                await sandbox.write_file(file_path, new_content)
                await self._notify_fs_update([file_path])
                return f"✅ Applied changes to {file_path}"
            else:
                return f"❌ Changes to {file_path} were rejected"

        # Delegate other operations to base adapter
        return await self._base_adapter.execute_tool(ctx, name, args)

    async def _notify_fs_update(self, files: list[str]) -> None:
        """Send file system update notification."""
        await self._diff_service._send_event({
            "type": "event",
            "payload": {
                "action": "fs_update",
                "status": "executing",
                "data": files
            }
        })

    def handle_diff_response(self, response: str, diff_id: str | None = None) -> None:
        """Handle user response to diff confirmation.

        This is called from the WebSocket handler when user clicks
        approve/reject buttons.

        Args:
            response: "approve" or "reject"
            diff_id: Optional diff ID
        """
        if response == "yes" or response == "approve":
            self._diff_service.handle_user_response("approve", diff_id)
        elif response == "no" or response == "reject":
            self._diff_service.handle_user_response("reject", diff_id)
