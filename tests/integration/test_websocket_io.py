"""Tests for WebSocketIO thread-safe implementation."""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from agent_os.server.websocket_io import AiderExecutor, WebSocketIO


class TestWebSocketIO:
    """Test suite for WebSocketIO thread safety."""

    @pytest.mark.asyncio
    async def test_tool_output(self) -> None:
        """Test sending tool output to queue."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        io = WebSocketIO(queue, loop=loop)

        io.tool_output("Hello, World!")

        item = await queue.get()
        assert item["type"] == "event"
        assert item["payload"]["action"] == "log"
        assert item["payload"]["message"] == "Hello, World!"
        assert item["payload"]["status"] == "executing"

    @pytest.mark.asyncio
    async def test_get_input_flow(self) -> None:
        """Test the input flow with threading (blocking -> async)."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        io = WebSocketIO(queue, loop=loop)

        # Simulation of Aider running in a separate thread
        def run_aider_input() -> str:
            """This runs in executor thread (blocking)."""
            return io.get_input("What is your name?")

        with ThreadPoolExecutor(max_workers=1) as executor:
            # Submit the blocking task to a thread
            future = executor.submit(run_aider_input)

            # Wait for the request event on the queue
            request = await asyncio.wait_for(queue.get(), timeout=2.0)
            assert request["type"] == "event"
            assert request["payload"]["action"] == "request_input"
            assert request["payload"]["data"]["prompt"] == "What is your name?"

            # Simulate user input arriving from WebSocket
            io.receive_input("Alice")

            # Wait for the blocking call to complete
            result = await asyncio.wrap_future(future)
            assert result == "Alice"

    @pytest.mark.asyncio
    async def test_concurrent_input_output(self) -> None:
        """Test concurrent input/output operations (thread safety)."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        io = WebSocketIO(queue, loop=loop)

        results: list[str] = []
        errors: list[Exception] = []

        def producer_thread() -> None:
            """Thread that produces output."""
            try:
                for i in range(3):
                    io.tool_output(f"Message {i}")
                    time.sleep(0.05)  # Slightly longer delay to avoid event loop congestion
            except Exception as e:
                errors.append(e)

        def consumer_thread() -> None:
            """Thread that requests input."""
            try:
                for i in range(2):
                    response = io.get_input(f"Prompt {i}?")
                    results.append(response)
                    time.sleep(0.05)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=2) as executor:
            # Start both threads
            producer_future = executor.submit(producer_thread)
            consumer_future = executor.submit(consumer_thread)

            # Process events and provide input
            inputs_received = 0
            outputs_received = 0

            while outputs_received < 3 or inputs_received < 2:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=2.0)
                    action = event["payload"]["action"]

                    if action == "log":
                        outputs_received += 1
                    elif action == "request_input":
                        io.receive_input(f"Response {inputs_received}")
                        inputs_received += 1
                except TimeoutError:
                    break

            # Wait for threads to complete (with longer timeout)
            producer_future.result(timeout=5.0)
            consumer_future.result(timeout=5.0)

        # Verify results
        assert len(results) == 2
        assert results == ["Response 0", "Response 1"]
        assert not errors

    @pytest.mark.asyncio
    async def test_input_timeout(self) -> None:
        """Test that get_input times out appropriately."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        io = WebSocketIO(queue, loop=loop)

        def slow_input() -> str:
            return io.get_input("Prompt?")

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(slow_input)

            # Get the request event
            await queue.get()

            # Don't provide input - should timeout
            # Note: The default timeout is 300 seconds, so we manually test
            # by checking that the future doesn't complete immediately
            done, _ = await asyncio.wait(
                [asyncio.wrap_future(future)],
                timeout=0.1,
                return_when=asyncio.FIRST_COMPLETED
            )
            assert not done

            # Clean up - provide input to allow thread to exit
            io.receive_input("cleanup")
            await asyncio.wrap_future(future)

    @pytest.mark.asyncio
    async def test_confirm_ask_non_blocking(self) -> None:
        """Test that confirm_ask doesn't block (for now)."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        io = WebSocketIO(queue, loop=loop)

        # confirm_ask should return True for "y" default
        result = io.confirm_ask("Continue?", default="y")
        assert result is True

        # Should return False for "n" default
        result = io.confirm_ask("Continue?", default="n")
        assert result is False

        # Check that event was sent
        event = await queue.get()
        assert event["type"] == "event"
        assert event["payload"]["action"] == "confirm_ask"

    @pytest.mark.asyncio
    async def test_error_propagation(self) -> None:
        """Test that errors can be propagated to waiting get_input."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        io = WebSocketIO(queue, loop=loop)

        def waiting_input() -> str:
            return io.get_input("Prompt?")

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(waiting_input)

            # Wait for request
            await queue.get()

            # Send an error instead of input
            test_error = ValueError("User cancelled")
            io.receive_error(test_error)

            # Future should raise the error
            with pytest.raises(ValueError, match="User cancelled"):
                await asyncio.wrap_future(future)

    @pytest.mark.asyncio
    async def test_prompt_ask_delegates_to_get_input(self) -> None:
        """Test that prompt_ask delegates to get_input."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        io = WebSocketIO(queue, loop=loop)

        def call_prompt_ask() -> str:
            """Call prompt_ask from a thread (like Aider would)."""
            return io.prompt_ask("Enter value: ", default="default")

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(call_prompt_ask)

            # Wait for request event
            event = await asyncio.wait_for(queue.get(), timeout=2.0)
            assert event["payload"]["action"] == "request_input"

            # Provide input
            io.receive_input("user input")

            # Get result
            result = await asyncio.wrap_future(future)
            assert result == "user input"


class TestAiderExecutor:
    """Test suite for AiderExecutor."""

    @pytest.mark.asyncio
    async def test_ws_io_creation(self) -> None:
        """Test that ws_io property creates WebSocketIO."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        # Mock sandbox
        class MockSandbox:
            pass

        executor = AiderExecutor(MockSandbox(), queue, loop)

        # First access creates WebSocketIO
        assert executor._ws_io is None
        ws_io = executor.ws_io
        assert ws_io is not None
        assert isinstance(ws_io, WebSocketIO)

        # Second access returns same instance
        assert executor.ws_io is ws_io

    @pytest.mark.asyncio
    async def test_receive_input_forwarding(self) -> None:
        """Test that receive_input forwards to WebSocketIO."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        class MockSandbox:
            pass

        executor = AiderExecutor(MockSandbox(), queue, loop)
        executor.ws_io  # Initialize

        # Forward input
        executor.receive_input("test input")

        # The input should be in the buffer
        assert executor._ws_io._input_buffer == "test input"

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        """Test starting and stopping executor."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        class MockSandbox:
            pass

        executor = AiderExecutor(MockSandbox(), queue, loop)

        # Start should be idempotent
        await executor.start()
        await executor.start()  # Should not error

        # Stop should clean up
        await executor.stop()

    @pytest.mark.asyncio
    async def test_multiple_sequential_inputs(self) -> None:
        """Test multiple sequential get_input calls."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        io = WebSocketIO(queue, loop=loop)

        def get_multiple_inputs() -> list[str]:
            """Get multiple inputs in sequence."""
            results = []
            for i in range(3):
                results.append(io.get_input(f"Prompt {i}?"))
            return results

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(get_multiple_inputs)

            # Respond to each prompt
            for i in range(3):
                # Wait for request
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                assert event["payload"]["action"] == "request_input"

                # Provide input
                io.receive_input(f"Answer {i}")

            # Get results
            results = await asyncio.wrap_future(future)
            assert results == ["Answer 0", "Answer 1", "Answer 2"]
