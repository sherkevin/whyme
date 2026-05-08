"""Tests for AiderAdapter."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agent_os.capabilities.coding.aider_adapter import AiderAdapter
from agent_os.core.types import RuntimeContext


class TestAiderAdapter:
    """Test suite for AiderAdapter."""

    @pytest.fixture
    def adapter(self) -> AiderAdapter:
        return AiderAdapter()

    @pytest.fixture
    def context(self) -> RuntimeContext:
        return RuntimeContext(
            session_id="test_session",
            user_id="test_user",
            trace_id="test_trace",
        )

    @pytest.mark.asyncio
    async def test_apply_edit_run_command(
        self, 
        adapter: AiderAdapter, 
        context: RuntimeContext
    ) -> None:
        """Test running a command via apply_edit."""
        mock_sandbox = AsyncMock()
        mock_sandbox.run_command.return_value = "Output"

        with patch("agent_os.server.app._session_manager") as mock_mgr:
            mock_mgr.get_or_create_sandbox = AsyncMock(return_value=mock_sandbox)
            
            result = await adapter.apply_edit(context, "run: echo hello")
            
            mock_sandbox.run_command.assert_called_with("echo hello")
            assert result == "Output"

    @pytest.mark.asyncio
    async def test_apply_edit_write_file(
        self, 
        adapter: AiderAdapter, 
        context: RuntimeContext
    ) -> None:
        """Test writing a file via apply_edit."""
        mock_sandbox = AsyncMock()
        
        with patch("agent_os.server.app._session_manager") as mock_mgr:
            mock_mgr.get_or_create_sandbox = AsyncMock(return_value=mock_sandbox)
            
            result = await adapter.apply_edit(context, "write: test.py print('hello')")
            
            mock_sandbox.write_file.assert_called_with("test.py", "print('hello')")
            assert "successfully" in result

    def test_local_repo_map(self, adapter: AiderAdapter, tmp_path: Any) -> None:
        """Test generating a map for a local directory."""
        # Create some structure
        d = tmp_path / "subdir"
        d.mkdir()
        p = d / "hello.txt"
        p.write_text("content")
        
        repo_map = adapter.generate_repo_map(str(tmp_path))
        
        assert "subdir" in repo_map
        assert "hello.txt" in repo_map
