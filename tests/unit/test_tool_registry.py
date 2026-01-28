"""Tests for ToolRegistry."""

import asyncio
from typing import Any

import pytest

from agent_os.tools import ToolRegistryImpl


class TestToolRegistry:
    """Test suite for ToolRegistry."""

    @pytest.fixture
    async def registry(self) -> ToolRegistryImpl:
        """Create a fresh registry for each test."""
        reg = ToolRegistryImpl()
        yield reg
        await reg.shutdown()

    @pytest.mark.asyncio
    async def test_register_python_function(self, registry: ToolRegistryImpl) -> None:
        """Test registering a Python function."""

        def add_numbers(a: int, b: int) -> int:
            """Add two numbers together."""
            return a + b

        await registry.register_python_tool(add_numbers)

        definitions = await registry.get_definitions()
        assert len(definitions) == 1
        assert definitions[0]["function"]["name"] == "add_numbers"
        assert definitions[0]["function"]["description"] == "Add two numbers together."
        assert "a" in definitions[0]["function"]["parameters"]["properties"]
        assert "b" in definitions[0]["function"]["parameters"]["properties"]

    @pytest.mark.asyncio
    async def test_execute_python_tool(self, registry: ToolRegistryImpl) -> None:
        """Test executing a Python tool."""

        def greet(name: str) -> str:
            """Greet someone by name."""
            return f"Hello, {name}!"

        await registry.register_python_tool(greet)

        result = await registry.execute("greet", {"name": "World"})
        assert result == "Hello, World!"

    @pytest.mark.asyncio
    async def test_execute_python_tool_with_exception(self, registry: ToolRegistryImpl) -> None:
        """Test executing a Python tool that raises an exception."""

        def failing_tool() -> str:
            """A tool that always fails."""
            raise ValueError("This tool fails")

        await registry.register_python_tool(failing_tool)

        result = await registry.execute("failing_tool", {})
        assert "error" in result
        assert result["tool"] == "failing_tool"

    @pytest.mark.asyncio
    async def test_execute_async_python_tool(self, registry: ToolRegistryImpl) -> None:
        """Test executing an async Python tool."""

        async def async_greet(name: str) -> str:
            """Asynchronously greet someone."""
            await asyncio.sleep(0.01)
            return f"Async hello, {name}!"

        await registry.register_python_tool(async_greet)

        result = await registry.execute("async_greet", {"name": "World"})
        assert result == "Async hello, World!"

    @pytest.mark.asyncio
    async def test_register_mcp(self, registry: ToolRegistryImpl) -> None:
        """Test registering an MCP server."""
        await registry.register_mcp(
            name="test_mcp",
            command="echo",
            args=["hello"],
        )

        definitions = await registry.get_definitions()
        assert len(definitions) == 1
        assert definitions[0]["function"]["name"] == "test_mcp"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(self, registry: ToolRegistryImpl) -> None:
        """Test executing a tool that doesn't exist."""
        with pytest.raises(ValueError, match="Tool not found"):
            await registry.execute("nonexistent_tool", {})

    @pytest.mark.asyncio
    async def test_multiple_tools(self, registry: ToolRegistryImpl) -> None:
        """Test registering multiple tools."""

        def tool_a(x: int) -> int:
            """Tool A."""
            return x * 2

        def tool_b(y: str) -> str:
            """Tool B."""
            return y.upper()

        await registry.register_python_tool(tool_a)
        await registry.register_python_tool(tool_b)

        definitions = await registry.get_definitions()
        assert len(definitions) == 2

        result_a = await registry.execute("tool_a", {"x": 5})
        assert result_a == 10

        result_b = await registry.execute("tool_b", {"y": "hello"})
        assert result_b == "HELLO"

    @pytest.mark.asyncio
    async def test_tool_with_optional_parameters(self, registry: ToolRegistryImpl) -> None:
        """Test tool with optional parameters."""

        def greet_with_title(name: str, title: str = "Mr.") -> str:
            """Greet someone with a title."""
            return f"Hello, {title} {name}!"

        await registry.register_python_tool(greet_with_title)

        definitions = await registry.get_definitions()
        # name should be required, title should be optional
        params = definitions[0]["function"]["parameters"]
        assert "name" in params["required"]
        assert "title" not in params["required"]

        # Test with just the required parameter
        result = await registry.execute("greet_with_title", {"name": "Smith"})
        assert result == "Hello, Mr. Smith!"

    @pytest.mark.asyncio
    async def test_tool_with_various_types(self, registry: ToolRegistryImpl) -> None:
        """Test that different parameter types generate correct schema."""

        def multi_type_tool(
            count: int, price: float, active: bool, tags: list
        ) -> dict[str, Any]:
            """Tool with various parameter types."""
            return {"count": count, "price": price, "active": active, "tags": tags}

        await registry.register_python_tool(multi_type_tool)

        definitions = await registry.get_definitions()
        props = definitions[0]["function"]["parameters"]["properties"]

        assert props["count"]["type"] == "integer"
        assert props["price"]["type"] == "number"
        assert props["active"]["type"] == "boolean"
        assert props["tags"]["type"] == "array"


    @pytest.mark.asyncio
    async def test_shutdown(self, registry: ToolRegistryImpl) -> None:
        """Test that shutdown cleans up resources."""
        # This test mainly ensures shutdown doesn't raise
        await registry.register_mcp("test", "echo", ["hello"])
        await registry.shutdown()
        # Should be able to call shutdown again without error
        await registry.shutdown()

    @pytest.mark.asyncio
    async def test_hot_reload(self, registry: ToolRegistryImpl, tmp_path: Any) -> None:
        """Test loading tools from a directory."""
        # Create a tool file
        tool_file = tmp_path / "my_tools.py"
        tool_file.write_text("""
from agent_os.tools.registry import tool

@tool
def dynamic_add(a: int, b: int) -> int:
    "Add numbers dynamically."
    return a + b

def ignored_helper():
    pass
""")
        
        await registry.load_tools_from_directory(str(tmp_path))
        
        # Verify tool is registered
        definitions = await registry.get_definitions()
        names = [d["function"]["name"] for d in definitions]
        assert "dynamic_add" in names
        assert "ignored_helper" not in names
        
        # Verify execution
        result = await registry.execute("dynamic_add", {"a": 10, "b": 20})
        assert result == 30

