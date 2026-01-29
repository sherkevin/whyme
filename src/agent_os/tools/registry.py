"""Tool registry for managing Python functions and MCP tools."""

from __future__ import annotations

import asyncio
import json
from inspect import Parameter, Signature, signature
from typing import Any, Callable

from agent_os.core.interfaces import ToolRegistry
import importlib.util
import os
import sys
from pathlib import Path

# Import MCPBridge for MCP integration
try:
    from global_toolkit.bridge import MCPBridge
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MCPBridge = None

def tool(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to mark a function as a tool."""
    func._is_tool = True  # type: ignore
    return func


def _generate_schema_from_signature(func: Callable[..., Any]) -> dict[str, Any]:
    """Generate OpenAI function calling schema from a Python function signature.

    Args:
        func: The function to generate schema from

    Returns:
        OpenAI function definition schema
    """
    sig = signature(func)
    parameters: dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    for name, param in sig.parameters.items():
        param_type = param.annotation

        # Skip self parameter for methods
        if name == "self":
            continue

        # Map Python types to JSON Schema types
        json_type = "string"
        description = ""
        enum = None

        if param_type == int:
            json_type = "integer"
        elif param_type == float:
            json_type = "number"
        elif param_type == bool:
            json_type = "boolean"
        elif param_type == list:
            json_type = "array"
        elif param_type == dict:
            json_type = "object"

        # Check for default value
        has_default = param.default != Parameter.empty

        param_schema: dict[str, Any] = {"type": json_type}
        if enum:
            param_schema["enum"] = enum

        parameters["properties"][name] = param_schema

        if not has_default and name != "kwargs":
            parameters["required"].append(name)

    # Handle docstring
    description = func.__doc__ or func.__name__.replace("_", " ").title()
    if description == "None":
        description = func.__name__

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": parameters,
        },
    }


class MCPTool:
    """Represents an MCP tool with its connection info."""

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str],
        tool_definition: dict[str, Any],
        server_name: str | None = None,
    ) -> None:
        self.name = name
        self.command = command
        self.args = args
        self.definition = tool_definition
        self.server_name = server_name or name  # Track which MCP server
        self.process: asyncio.subprocess.Process | None = None


class PythonTool:
    """Represents a Python function tool."""

    def __init__(self, func: Callable[..., Any], name: str | None = None) -> None:
        self.func = func
        self.name = name or func.__name__
        self.schema = _generate_schema_from_signature(func)


class ToolRegistryImpl(ToolRegistry):
    """Implementation of ToolRegistry supporting Python functions and MCP."""

    def __init__(self) -> None:
        self._python_tools: dict[str, PythonTool] = {}
        self._mcp_tools: dict[str, MCPTool] = {}
        self._mcp_processes: dict[str, asyncio.subprocess.Process] = {}

        # Initialize MCPBridge if available
        self._mcp_bridge: MCPBridge | None = None
        if MCP_AVAILABLE:
            self._mcp_bridge = MCPBridge()
            print("[ToolRegistry] MCPBridge initialized successfully")

    async def register_python_tool(self, func: Callable[..., Any]) -> None:
        """Register a Python function as a tool."""
        tool = PythonTool(func)
        self._python_tools[tool.name] = tool

    async def register_mcp(self, name: str, command: str, args: list[str]) -> None:
        """Register an MCP server and discover its tools.

        Uses MCPBridge to list available tools from the MCP server.
        """
        # Use MCPBridge to discover tools if available
        if self._mcp_bridge:
            try:
                # Start the MCP server process
                await self._mcp_bridge.start_server(name, command, args)

                # List available tools from this MCP server
                tools = await self._mcp_bridge.list_tools(name)

                # Register each tool with its full definition
                for tool_def in tools:
                    tool_name = tool_def.get("name", f"{name}_{tool_def.get('name', 'unknown')}")
                    self._mcp_tools[tool_name] = MCPTool(
                        name=tool_name,
                        command=command,
                        args=args,
                        server_name=name,  # Track which server this tool belongs to
                        tool_definition=tool_def
                    )
                    print(f"[ToolRegistry] Registered MCP tool: {tool_name} from server {name}")

                print(f"[ToolRegistry] Successfully registered {len(tools)} tools from MCP server {name}")
                return

            except Exception as e:
                print(f"[ToolRegistry] Failed to discover MCP tools from {name}: {e}")
                # Fall back to placeholder registration

        # Fallback: Create a placeholder definition
        self._mcp_tools[name] = MCPTool(
            name=name,
            command=command,
            args=args,
            server_name=name,
            tool_definition={
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"MCP tool: {name}",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        )
        print(f"[ToolRegistry] Registered MCP server {name} with placeholder tool")

    async def get_definitions(self) -> list[dict[str, Any]]:
        """Return all tool definitions in OpenAI format."""
        definitions: list[dict[str, Any]] = []

        # Add Python tools
        for tool in self._python_tools.values():
            definitions.append(tool.schema)

        # Add MCP tools
        for tool in self._mcp_tools.values():
            definitions.append(tool.definition)

        return definitions

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name."""
        # Check Python tools first
        if tool_name in self._python_tools:
            tool = self._python_tools[tool_name]
            try:
                return await self._execute_python_tool(tool, arguments)
            except Exception as e:
                return {"error": str(e), "tool": tool_name}

        # Check MCP tools
        if tool_name in self._mcp_tools:
            return await self._execute_mcp_tool(tool_name, arguments)

        raise ValueError(f"Tool not found: {tool_name}")

    async def _execute_python_tool(
        self, tool: PythonTool, arguments: dict[str, Any]
    ) -> Any:
        """Execute a Python tool."""
        func = tool.func
        # Check if function is async
        if asyncio.iscoroutinefunction(func):
            return await func(**arguments)
        else:
            # Run synchronous function in executor to avoid blocking
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: func(**arguments))

    async def _execute_mcp_tool(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """Execute an MCP tool via JSON-RPC using MCPBridge."""
        tool = self._mcp_tools[tool_name]

        # Use MCPBridge if available
        if self._mcp_bridge:
            try:
                # Call the tool via MCPBridge
                result = await self._mcp_bridge.call_tool(
                    server_name=tool.server_name,
                    tool_name=tool_name,
                    arguments=arguments
                )
                return result
            except Exception as e:
                return {"error": f"MCP tool execution failed: {str(e)}", "tool": tool_name}
        else:
            # Fallback: Use old method
            # Ensure MCP process is running
            process = await self._ensure_mcp_process(tool)

        # Send JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        try:
            # Write request to stdin
            assert process.stdin is not None
            process.stdin.write((json.dumps(request) + "\n").encode())
            await process.stdin.drain()

            # Read response with timeout
            response_line = await asyncio.wait_for(
                process.stdout.readline(),  # type: ignore[arg-type]
                timeout=30.0,
            )
            response = json.loads(response_line.decode())

            if "error" in response:
                raise RuntimeError(f"MCP error: {response['error']}")

            return response.get("result", {})
        except asyncio.TimeoutError:
            # Restart process on timeout
            await self._kill_mcp_process(tool_name)
            raise TimeoutError(f"MCP tool {tool_name} timed out")

    async def _ensure_mcp_process(
        self, tool: MCPTool
    ) -> asyncio.subprocess.Process:
        """Ensure MCP process is running, starting it if necessary."""
        if tool.name in self._mcp_processes:
            process = self._mcp_processes[tool.name]
            # Check if process is still alive
            if process.returncode is None:
                return process
            # Process died, remove it
            del self._mcp_processes[tool.name]

        # Start new process
        process = await asyncio.create_subprocess_exec(
            tool.command,
            *tool.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._mcp_processes[tool.name] = process

        # Give it a moment to start
        await asyncio.sleep(0.1)

        return process

    async def _kill_mcp_process(self, tool_name: str) -> None:
        """Kill an MCP process."""
        if tool_name in self._mcp_processes:
            process = self._mcp_processes.pop(tool_name)
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def shutdown(self) -> None:
        """Shutdown all MCP processes."""
        for tool_name in list(self._mcp_processes.keys()):
            await self._kill_mcp_process(tool_name)

    async def load_tools_from_directory(self, path: str) -> None:
        """Load tools from Python files in a directory.
        
        Loads modules and registers functions decorated with @tool.
        If no functions are decorated, registers all public functions.
        """
        directory = Path(path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {path}")
            
        for file_path in directory.glob("*.py"):
            if file_path.name.startswith("_"):
                continue
                
            module_name = f"dynamic_tools.{file_path.stem}"
            
            # Load module dynamically
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # Scan for tools
                found_tools = [
                    obj for name, obj in vars(module).items()
                    if callable(obj) and getattr(obj, "_is_tool", False)
                ]
                
                # If no decorated tools, register all public functions
                if not found_tools:
                    found_tools = [
                        obj for name, obj in vars(module).items()
                        if callable(obj) 
                        and not name.startswith("_") 
                        and obj.__module__ == module.__name__  # Only functions defined in this module
                    ]
                
                for func in found_tools:
                    await self.register_python_tool(func)


__all__ = ["ToolRegistryImpl", "ToolRegistry", "tool"]
