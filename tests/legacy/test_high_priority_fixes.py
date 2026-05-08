"""Test high priority fixes for WebSocketIO, Diff confirmation, and Aider integration."""

import asyncio

import pytest

from agent_os.capabilities.coding.aider_integration import AiderCoderIntegration
from agent_os.server.diff_service import DiffService
from agent_os.server.websocket_io import WebSocketIO


class TestWebSocketIOConfirmAsk:
    """Test WebSocketIO confirm_ask method."""

    @pytest.mark.asyncio
    async def test_confirm_ask_with_response(self):
        """Test that confirm_ask blocks and receives response."""
        output_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        ws_io = WebSocketIO(output_queue, loop, pretty=True)

        # Start confirm_ask in background
        task = asyncio.create_task(
            asyncio.to_thread(ws_io.confirm_ask, "Do you want to continue?", default="y")
        )

        # Wait a bit for confirm_ask to send event
        await asyncio.sleep(0.1)

        # Check that event was sent
        event = await output_queue.get()
        assert event["type"] == "event"
        assert event["payload"]["action"] == "confirm_ask"
        assert event["payload"]["data"]["question"] == "Do you want to continue?"
        confirm_id = event["payload"]["data"]["confirm_id"]

        # Send response
        ws_io.receive_confirm_response(confirm_id, True)

        # Wait for confirm_ask to complete
        result = await task
        assert result is True

    @pytest.mark.asyncio
    async def test_confirm_ask_timeout(self):
        """Test that confirm_ask times out after timeout period."""
        output_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        ws_io = WebSocketIO(output_queue, loop, pretty=True)

        # Set a short timeout
        import threading
        original_wait = threading.Event.wait

        def mock_wait(self, timeout=None):
            # Always timeout
            return original_wait(self, timeout=0.001)

        threading.Event.wait = mock_wait

        try:
            with pytest.raises(TimeoutError):
                ws_io.confirm_ask("Test question", default="y")
        finally:
            threading.Event.wait = original_wait


class TestDiffService:
    """Test DiffService functionality."""

    @pytest.mark.asyncio
    async def test_propose_change_approved(self):
        """Test diff proposal with approval."""
        output_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        diff_service = DiffService("test_session", output_queue, loop)

        # Propose a change
        original = "line 1\nline 2\n"
        new = "line 1\nline 2 modified\n"

        # Start proposal in background
        task = asyncio.create_task(
            diff_service.propose_change("test.txt", original, new, "Modify line 2")
        )

        # Wait for event
        event = await output_queue.get()
        assert event["payload"]["action"] == "confirm_diff"
        assert event["payload"]["data"]["file"] == "test.txt"

        # Approve the change
        diff_service.handle_user_response("approve", None)

        # Check result
        approved = await task
        assert approved is True

    @pytest.mark.asyncio
    async def test_propose_change_rejected(self):
        """Test diff proposal with rejection."""
        output_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        diff_service = DiffService("test_session", output_queue, loop)

        # Propose a change
        original = "line 1\nline 2\n"
        new = "line 1\nline 2 modified\n"

        # Start proposal in background
        task = asyncio.create_task(
            diff_service.propose_change("test.txt", original, new, "Modify line 2")
        )

        # Wait for event
        await output_queue.get()

        # Reject the change
        diff_service.handle_user_response("reject", None)

        # Check result
        approved = await task
        assert approved is False

    @pytest.mark.asyncio
    async def test_generate_unified_diff(self):
        """Test diff generation."""
        output_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        diff_service = DiffService("test_session", output_queue, loop)

        original = "line 1\nline 2\nline 3\n"
        new = "line 1\nline 2 modified\nline 3\n"

        diff = diff_service._generate_unified_diff("test.txt", original, new)

        assert "--- a/test.txt" in diff
        assert "+++ b/test.txt" in diff
        assert "-line 2" in diff
        assert "+line 2 modified" in diff


class TestAiderIntegration:
    """Test Aider Coder integration."""

    @pytest.mark.asyncio
    async def test_webio_confirm_ask_uses_ws_io(self):
        """Test that WebIO.confirm_ask uses WebSocketIO when available."""
        output_queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        integration = AiderCoderIntegration(
            workspace_root="/tmp/test_workspace",
            model_name="gpt-4",
            output_queue=output_queue,
            event_loop=loop
        )

        # Initialize (this creates WebIO and WebSocketIO)
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            await integration.initialize()

            # Check that WebSocketIO was created
            assert integration._ws_io is not None
            assert isinstance(integration._ws_io, WebSocketIO)

            # Check that WebIO has reference to parent
            assert integration.io._parent is integration

    @pytest.mark.asyncio
    async def test_aider_agent_sets_websocket_params(self):
        """Test that AiderAgent can be configured with WebSocket parameters."""
        import tempfile

        from agent_os.agent_aider import AiderAgent
        from agent_os.core.config import load_config

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AiderAgent(
                session_id="test_session",
                workspace_root=tmpdir,
                config=load_config("config.yaml")
            )

            # Set WebSocket parameters
            output_queue = asyncio.Queue()
            loop = asyncio.get_event_loop()
            agent._output_queue = output_queue
            agent._event_loop = loop

            # Get aider integration (should use WebSocket parameters)
            aider = await agent._get_aider()

            # Check that parameters were passed
            assert aider._output_queue is output_queue
            assert aider._event_loop is loop


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
