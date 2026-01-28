"""Aider adapter implementation for coding capability."""

from __future__ import annotations

from typing import Any, List, Dict

from agent_os.capabilities.coding._vendor.repo_map import RepoMap
from agent_os.core.interfaces import CodingCapability
from agent_os.core.types import RuntimeContext


class AiderAdapter(CodingCapability):
    """Adapter for Aider coding capability."""

    async def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file. Overwrites existing content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "The file path relative to workspace root"},
                            "content": {"type": "string", "description": "The full content to write to the file"}
                        },
                        "required": ["path", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_command",
                    "description": "Run a shell command in the sandbox.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string", "description": "The shell command to execute"}
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read content from a file.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "The file path relative to workspace root"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "The directory path (default .)"}
                        },
                        "required": []
                    }
                }
            }
        ]

    async def apply_edit(self, ctx: RuntimeContext, instructions: str) -> str:
        """Legacy method for backward compatibility."""
        if instructions.startswith("run: "):
            return await self._execute_tool(ctx, "run_command", {"command": instructions[5:]})
        elif instructions.startswith("write: "):
            parts = instructions[7:].split(" ", 1)
            if len(parts) == 2:
                return await self._execute_tool(ctx, "write_file", {"path": parts[0], "content": parts[1]})
        
        return await self._execute_tool(ctx, "run_command", {"command": f"echo 'Use specific tools instead: {instructions}'"})

    async def execute_tool(self, ctx: RuntimeContext, name: str, args: Dict[str, Any]) -> str:
        """Execute a tool provided by this capability."""
        return await self._execute_tool(ctx, name, args)

    async def _execute_tool(self, ctx: RuntimeContext, name: str, args: Dict[str, Any]) -> str:
        from agent_os.server.app import _session_manager
        
        if not ctx.session_id:
            raise ValueError("Session ID required for coding capability")

        sandbox = await _session_manager.get_or_create_sandbox(ctx.session_id)

        # Notify frontend about file system changes (Simple approach: trigger event)
        # In a real event bus system, we would publish an event.
        # Here we can try to get the callback handler if accessible, or rely on client polling.
        # But for "automatic generation", we should probably return a structured result 
        # that the Agent can use to tell the user "I created file X".

        result = ""
        if name == "write_file":
            await sandbox.write_file(args["path"], args["content"])
            result = f"File {args['path']} written successfully."
            
        elif name == "run_command":
            result = await sandbox.run_command(args["command"])
            
        elif name == "read_file":
            result = await sandbox.read_file(args["path"])
            
        elif name == "list_files":
            path = args.get("path", ".")
            result = await sandbox.run_command(f"ls -R {path}")
        else:
            result = f"Unknown tool: {name}"

        # Send a filesystem update event to the frontend
        try:
            diff_service = _session_manager.get_diff_service(ctx.session_id)
            if diff_service:
                # We reuse the diff service queue or direct websocket if we had access.
                # Since we don't have direct access to the websocket here easily without passing it down,
                # we rely on the fact that file changes will be visible on next refresh.
                # BUT, to make it "automatic", we should try to push an event.
                # Let's see if we can get the event loop and queue from session manager.
                if ctx.session_id in _session_manager._output_queues:
                    queue = _session_manager._output_queues[ctx.session_id]
                    await queue.put({
                        "type": "event",
                        "payload": {
                            "action": "fs_update",
                            "message": f"File system updated: {name} {args.get('path', '')}"
                        }
                    })
        except Exception as e:
            print(f"Failed to send fs_update: {e}")

        return result

    def generate_repo_map(self, root_dir: str) -> str:
        """Generate repository map for a local directory.
        
        This is kept for compatibility/testing of the vendor component.
        """
        mapper = RepoMap(root_dir)
        return mapper.get_repo_map()
