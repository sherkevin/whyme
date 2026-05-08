"""Tests for FullAiderAdapter integration."""

from __future__ import annotations

import asyncio
import os

import pytest

from agent_os.capabilities.coding.full_aider_adapter import AiderCoderFactory, FullAiderAdapter

# Check if Aider is available
AIDER_AVAILABLE = False
try:
    import aider
    AIDER_AVAILABLE = True
except ImportError:
    pass


class TestAiderCoderFactory:
    """Test suite for Aider Coder factory."""

    @pytest.mark.asyncio
    async def test_create_adapter(self) -> None:
        """Test creating an adapter via factory."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        # Mock sandbox
        class MockSandbox:
            workspace_root = "./data/test_workspace"

        sandbox = MockSandbox()

        # Create adapter
        adapter = await AiderCoderFactory.create(
            sandbox=sandbox,
            output_queue=queue,
            loop=loop,
            model="gpt-4",
        )

        assert adapter is not None
        assert isinstance(adapter, FullAiderAdapter)
        assert adapter.model == "gpt-4"

        # Clean up
        await adapter.cleanup()


class TestFullAiderAdapter:
    """Test suite for FullAiderAdapter."""

    @pytest.mark.asyncio
    async def test_get_tool_definitions(self) -> None:
        """Test getting tool definitions."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        class MockSandbox:
            workspace_root = "./data/test_workspace"

        adapter = FullAiderAdapter(
            sandbox=MockSandbox(),
            ws_io=type("MockWSIO", (), {"tool_output": lambda m: None})(),
            model="gpt-4",
        )

        definitions = await adapter.get_tool_definitions()

        assert len(definitions) > 0
        tool_names = [d["function"]["name"] for d in definitions]
        assert "aider_edit" in tool_names
        assert "aider_read_file" in tool_names
        assert "aider_git_status" in tool_names
        assert "aider_repo_map" in tool_names

    @pytest.mark.asyncio
    async def test_workspace_path_resolution(self) -> None:
        """Test workspace path resolution."""
        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        # LocalSandbox
        class LocalSandbox:
            workspace_root = "./data/test_local"

        local_adapter = FullAiderAdapter(
            sandbox=LocalSandbox(),
            ws_io=type("MockWSIO", (), {})(),
            model="gpt-4",
        )

        path = local_adapter._get_workspace_path("test.py")
        assert path.endswith("test_local" + os.sep + "test.py")

        # DockerSandbox (style)
        class DockerSandbox:
            workspace = "/workspace"

        docker_adapter = FullAiderAdapter(
            sandbox=DockerSandbox(),
            ws_io=type("MockWSIO", (), {})(),
            model="gpt-4",
        )

        path = docker_adapter._get_workspace_path("test.py")
        # On Windows, os.path.join will use backslash
        assert "workspace" in path and "test.py" in path

    @pytest.mark.asyncio
    async def test_git_status_command(self) -> None:
        """Test git status command execution."""
        class MockSandbox:
            workspace_root = "./data/test_workspace"
            async def run_command(self, cmd: str) -> str:
                if "status" in cmd:
                    return "On branch main\nnothing to commit"
                return ""

        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        adapter = FullAiderAdapter(
            sandbox=MockSandbox(),
            ws_io=type("MockWSIO", (), {})(),
            model="gpt-4",
        )

        result = await adapter._aider_git_status()
        assert "main" in result

    @pytest.mark.asyncio
    async def test_repo_map(self) -> None:
        """Test repository map generation."""
        import os
        import tempfile

        # Create temporary workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test files
            test_file = os.path.join(tmpdir, "test.py")
            with open(test_file, "w") as f:
                f.write("def hello():\n    print('hello')\n")

            class MockSandbox:
                workspace_root = tmpdir

            queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
            loop = asyncio.get_running_loop()

            adapter = FullAiderAdapter(
                sandbox=MockSandbox(),
                ws_io=type("MockWSIO", (), {})(),
                model="gpt-4",
            )

            result = await adapter._aider_repo_map()
            assert isinstance(result, str)
            # Should contain some representation of the file

    @pytest.mark.asyncio
    async def test_execute_tool_dispatch(self) -> None:
        """Test that execute_tool dispatches to correct methods."""
        class MockSandbox:
            workspace_root = "./data/test_workspace"
            async def run_command(self, cmd: str) -> str:
                return f"Executed: {cmd}"

        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        adapter = FullAiderAdapter(
            sandbox=MockSandbox(),
            ws_io=type("MockWSIO", (), {})(),
            model="gpt-4",
        )

        # Test git_status tool
        result = await adapter.execute_tool(
            type("MockCtx", (), {"session_id": "test"})(),
            "aider_git_status",
            {}
        )
        assert "Executed" in result

        # Test unknown tool
        result = await adapter.execute_tool(
            type("MockCtx", (), {"session_id": "test"})(),
            "unknown_tool",
            {}
        )
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    @pytest.mark.skipif(not AIDER_AVAILABLE, reason="Aider not installed")
    async def test_legacy_apply_edit(self) -> None:
        """Test legacy apply_edit method."""
        class MockSandbox:
            workspace_root = "./data/test_workspace"
            async def run_command(self, cmd: str) -> str:
                return f"Executed: {cmd}"

        queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        adapter = FullAiderAdapter(
            sandbox=MockSandbox(),
            ws_io=type("MockWSIO", (), {})(),
            model="gpt-4",
        )

        # This should work without files
        result = await adapter.apply_edit(
            type("MockCtx", (), {"session_id": "test"})(),
            "Add error handling"
        )
        assert isinstance(result, str)
