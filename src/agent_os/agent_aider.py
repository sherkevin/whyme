"""Aider-based Agent - directly uses aider's Coder for all coding tasks."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from agent_os.core.config import Config, load_config
from agent_os.core.interfaces import AgentCallbackHandler
from agent_os.core.types import RuntimeContext


class AiderAgent:
    """Agent that directly uses aider's Coder for all operations."""

    def __init__(self, session_id: str, workspace_root: str, config: Config | None = None):
        """Initialize the AiderAgent.

        Args:
            session_id: Unique session identifier
            workspace_root: Path to the workspace directory
            config: Optional configuration
        """
        self.session_id = session_id
        self.workspace_root = Path(workspace_root).resolve()
        self.config = config or load_config("config.yaml")

        # Aider integration will be initialized on first use
        self._aider_integration = None

        # WebSocket communication (will be set by chat method via callbacks)
        self._output_queue = None
        self._event_loop = None

    async def _get_aider(self):
        """Lazy initialization of aider integration."""
        if self._aider_integration is None:
            from agent_os.capabilities.coding.aider_integration import AiderCoderIntegration

            model_name = self.config.llm.config.get("model", "openai/DeepSeek-V3.1") if self.config.llm else "openai/DeepSeek-V3.1"

            self._aider_integration = AiderCoderIntegration(
                workspace_root=str(self.workspace_root),
                model_name=model_name,
                output_queue=self._output_queue,
                event_loop=self._event_loop
            )

            await self._aider_integration.initialize()

        return self._aider_integration

    async def chat(
        self,
        message: str,
        user_id: str = "default_user",
        session_id: str | None = None,
        callbacks: list[AgentCallbackHandler] | None = None,
    ) -> dict[str, Any]:
        """Send a message to aider and get a response.

        Unlike the standard Agent which uses LLM tools, this directly
        passes the message to aider's Coder which handles everything.
        """
        # Log to file
        with open("debug_aider_chat.log", "a", encoding="utf-8") as f:
            f.write(f"\nAiderAgent.chat() called: {message[:50]}...\n")

        callbacks = callbacks or []

        # Create runtime context
        ctx = RuntimeContext(
            session_id=session_id or self.session_id,
            user_id=user_id,
            trace_id=str(uuid.uuid4()),
        )

        # Notify we're processing
        for cb in callbacks:
            await cb.on_log(f"Processing with Aider: {message[:50]}...")

        try:
            # Get aider integration
            aider = await self._get_aider()

            # Check if this is a delete request and handle it directly
            # Simple keyword check - should work regardless of encoding display issues
            is_delete_request = (
                "删除" in message or "移除" in message or
                "delete" in message.lower() or "remove" in message.lower()
            )

            if is_delete_request:
                import os
                import re

                print(f"[DEBUG] Detected delete request: {message[:50]}")

                # Extract filenames from message - use simple string methods
                files_to_delete = set()

                # Method 1: Find all words that look like filenames (contain extension)
                # Match patterns like: test.txt, file.py, etc.
                filename_pattern = r'[\w\-]+\.[\w]+'
                potential_files = re.findall(filename_pattern, message)
                files_to_delete.update(potential_files)

                # Method 2: Split by common separators and check each part
                # This handles: "删除test.txt和websocket_test.txt"
                separators = ['和', '与', ',', '，', ' ', '和']
                for sep in separators:
                    parts = message.split(sep)
                    for part in parts:
                        # Remove keywords
                        clean_part = part.strip()
                        for kw in ['删除', '移除', 'delete', 'remove']:
                            if clean_part.startswith(kw):
                                clean_part = clean_part[len(kw):].strip()
                        # Check if it looks like a filename
                        if '.' in clean_part and len(clean_part) < 100:
                            files_to_delete.add(clean_part)

                print(f"[DEBUG] Files to delete: {files_to_delete}")

                if files_to_delete:
                    deleted_files = []
                    for filename in files_to_delete:
                        file_path = self.workspace_root / filename
                        if file_path.exists():
                            try:
                                os.remove(file_path)
                                deleted_files.append(filename)
                                print(f"[DEBUG] Deleted file: {filename}")
                            except Exception as e:
                                print(f"[DEBUG] Failed to delete {filename}: {e}")

                    if deleted_files:
                        response = f"已删除 {len(deleted_files)} 个文件：{', '.join(deleted_files)}"
                        print(f"[DEBUG] Direct delete response: {response}")

                        # Safe print for Windows console
                        try:
                            print(f"[DEBUG] Deleted files: {', '.join(deleted_files)}")
                        except UnicodeEncodeError:
                            print(f"[DEBUG] Deleted {len(deleted_files)} files")

                        # Notify callbacks
                        for cb in callbacks:
                            await cb.on_agent_response(response)
                            await cb.on_log(f"Deleted files: {', '.join(deleted_files)}")

                        return {
                            "content": response,
                            "file_changes": [{"action": "delete", "path": f} for f in deleted_files],
                            "usage": {},
                        }

            # Run the message through aider
            print(f"[DEBUG] Running message through aider: {message[:50]}...")
            response = await aider.run_message(ctx, message)
            print(f"[DEBUG] Aider response: {response[:200] if len(response) > 200 else response}...")

            # Get file changes
            file_changes = aider.get_file_changes()

            # Notify callbacks
            for cb in callbacks:
                await cb.on_agent_response(response)

                # Notify about file changes
                for change in file_changes:
                    await cb.on_log(f"File {change['action']}: {change['path']}")

            return {
                "content": response,
                "file_changes": file_changes,
                "usage": {},  # Aider doesn't track usage the same way
            }

        except Exception as e:
            error_msg = f"Error in aider chat: {e}"
            print(f"[ERROR] {error_msg}")
            import traceback
            traceback.print_exc()

            for cb in callbacks:
                await cb.on_log(error_msg)

            return {
                "content": error_msg,
                "error": str(e),
                "usage": {},
            }

    async def add_file(self, filepath: str) -> None:
        """Add a file to the aider context."""
        aider = await self._get_aider()
        aider.add_file(filepath)

    def get_chat_history(self) -> list[dict[str, Any]]:
        """Get the chat history from aider."""
        if self._aider_integration:
            return self._aider_integration.get_chat_history()
        return []

    def reset_conversation(self) -> None:
        """Reset conversation history."""
        # For now, we'd need to recreate the aider integration
        # This is a placeholder
        self._aider_integration = None


__all__ = ["AiderAgent"]
