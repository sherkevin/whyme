"""Full Aider Coder integration for AgentOS.

This module provides a complete integration with Aider's Coder class,
using WebSocketIO for communication and enabling Git workflows.
"""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from agent_os.core.interfaces import CodingCapability
from agent_os.core.types import RuntimeContext
from agent_os.server.websocket_io import WebSocketIO


class FullAiderAdapter(CodingCapability):
    """Complete Aider Coder integration with WebSocketIO.

    This adapter creates a real Aider Coder instance and runs it in a
    background thread, using WebSocketIO for all user interactions.
    """

    def __init__(
        self,
        sandbox: Any,
        ws_io: WebSocketIO,
        model: str = "gpt-4",
        editor_model: str | None = None,
    ) -> None:
        """Initialize the full Aider adapter.

        Args:
            sandbox: Sandbox instance for file operations
            ws_io: WebSocketIO instance for communication
            model: Main model for code generation
            editor_model: Optional model for editing (defaults to model)
        """
        self.sandbox = sandbox
        self.ws_io = ws_io
        self.model = model
        self.editor_model = editor_model or model

        # Aider Coder instance (created on first use)
        self._coder: Any | None = None
        self._coder_lock = threading.Lock()

        # Thread pool for running Aider operations
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aider-")

    async def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Get tool definitions for Aider operations."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "aider_edit",
                    "description": "Edit files using Aider with AI assistance. "
                    "This will generate a diff and ask for confirmation before applying.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "instruction": {
                                "type": "string",
                                "description": "Natural language instruction for what changes to make"
                            },
                            "files": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of files to include in the edit context"
                            }
                        },
                        "required": ["instruction"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "aider_read_file",
                    "description": "Read a file using Aider's context-aware reader",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "File path relative to workspace"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "aider_git_status",
                    "description": "Get Git status of the workspace",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "aider_git_diff",
                    "description": "Get Git diff of changes",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string",
                                "description": "Optional specific file to diff"
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "aider_repo_map",
                    "description": "Get a repository map showing code structure",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            }
        ]

    async def execute_tool(
        self,
        ctx: RuntimeContext,
        name: str,
        args: dict[str, Any],
    ) -> str:
        """Execute an Aider tool."""
        try:
            if name == "aider_edit":
                return await self._aider_edit(
                    instruction=args.get("instruction", ""),
                    files=args.get("files", [])
                )
            elif name == "aider_read_file":
                return await self._aider_read_file(args.get("path", ""))
            elif name == "aider_git_status":
                return await self._aider_git_status()
            elif name == "aider_git_diff":
                return await self._aider_git_diff(args.get("file"))
            elif name == "aider_repo_map":
                return await self._aider_repo_map()
            else:
                return f"Unknown tool: {name}"
        except Exception as e:
            import traceback
            return f"Error executing {name}: {str(e)}\n{traceback.format_exc()}"

    async def _aider_edit(self, instruction: str, files: list[str]) -> str:
        """Run Aider edit operation.

        This creates a Coder instance, runs the edit instruction,
        and returns the result.

        Args:
            instruction: Natural language instruction for changes
            files: List of files to include in context

        Returns:
            Result message
        """
        # Ensure coder is initialized
        coder = await self._get_coder()

        # Run edit in background thread
        loop = asyncio.get_event_loop()

        def run_edit() -> str:
            try:
                # Add files to context
                for file_path in files:
                    if os.path.exists(self._get_workspace_path(file_path)):
                        coder.abs_fnames.add(self._get_workspace_path(file_path))

                # Run the edit
                result = coder.run(with_message=instruction)
                return f"Edit completed: {instruction}"
            except Exception as e:
                return f"Edit failed: {str(e)}"

        result = await loop.run_in_executor(self._executor, run_edit)
        return result

    async def _aider_read_file(self, path: str) -> str:
        """Read file using Aider's context."""
        full_path = self._get_workspace_path(path)
        return await self.sandbox.read_file(path)

    async def _aider_git_status(self) -> str:
        """Get Git status of workspace."""
        return await self.sandbox.run_command("git status")

    async def _aider_git_diff(self, file: str | None) -> str:
        """Get Git diff."""
        cmd = "git diff"
        if file:
            cmd += f" {file}"
        return await self.sandbox.run_command(cmd)

    async def _aider_repo_map(self) -> str:
        """Generate repository map."""
        from agent_os.capabilities.coding._vendor.repo_map import RepoMap

        workspace = self._get_workspace_path()
        mapper = RepoMap(workspace)
        return mapper.get_repo_map()

    async def _get_coder(self) -> Any:
        """Get or create Aider Coder instance.

        This is run in a thread since Coder initialization is synchronous.
        """
        if self._coder is not None:
            return self._coder

        with self._coder_lock:
            if self._coder is not None:
                return self._coder

            # Import Aider
            try:
                from aider.coders import Coder
                from aider.io import InputOutput
            except ImportError:
                raise ImportError(
                    "Aider is not installed. Install with: pip install aider-chat"
                )

            # Create Coder instance with our WebSocketIO
            loop = asyncio.get_event_loop()

            def create_coder() -> Any:
                workspace = self._get_workspace_path()
                os.makedirs(workspace, exist_ok=True)

                # Use our WebSocketIO instead of Aider's default IO
                # The ws_io should already be configured

                coder = Coder.create(
                    io=self.ws_io,  # Use our WebSocketIO
                    main_model=self.model,
                    editor_model=self.editor_model,
                    fnames=[],  # No files initially
                    git_dname=workspace,  # Workspace as git directory
                    show_diffs=True,
                    auto_commits=False,
                    dirty_commits=False,
                )
                return coder

            # Run in executor thread
            self._coder = await loop.run_in_executor(self._executor, create_coder)
            return self._coder

    def _get_workspace_path(self, relative_path: str = "") -> str:
        """Get full workspace path."""
        if hasattr(self.sandbox, "workspace_root"):
            # LocalSandbox
            base = str(self.sandbox.workspace_root)
        elif hasattr(self.sandbox, "workspace"):
            # DockerSandbox or similar
            base = self.sandbox.workspace
        else:
            # Fallback
            base = "./data/workspace"

        if relative_path:
            return os.path.join(base, relative_path)
        return base

    async def apply_edit(self, ctx: RuntimeContext, instructions: str) -> str:
        """Legacy method for backward compatibility."""
        return await self._aider_edit(instructions, [])

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._coder:
            # Stop the coder if needed
            pass
        self._executor.shutdown(wait=True)


class AiderCoderFactory:
    """Factory for creating Aider Coder instances with proper configuration."""

    @staticmethod
    async def create(
        sandbox: Any,
        output_queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
        model: str = "gpt-4",
        editor_model: str | None = None,
    ) -> FullAiderAdapter:
        """Create a fully configured Aider adapter.

        Args:
            sandbox: Sandbox instance
            output_queue: Queue for WebSocket events
            loop: Asyncio event loop
            model: Main model
            editor_model: Optional editor model

        Returns:
            Configured FullAiderAdapter instance
        """
        # Create WebSocketIO
        ws_io = WebSocketIO(output_queue, loop=loop, pretty=True)

        # Create adapter
        adapter = FullAiderAdapter(
            sandbox=sandbox,
            ws_io=ws_io,
            model=model,
            editor_model=editor_model,
        )

        return adapter
