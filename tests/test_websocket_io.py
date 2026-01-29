"""Test suite for WebSocketIO thread safety."""

import asyncio
import threading
import time
from typing import Any

import pytest

from agent_os.server.websocket_io import WebSocketIO, AiderExecutor


class TestWebSocketIOThreadSafety:
    """Test suite for WebSocketIO thread safety."""

    @pytest.fixture
    def event_loop(self):
        """Create event loop for testing."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()

    @pytest.fixture
    def output_queue(self, event_loop):
        """Create output queue."""
        return asyncio.Queue()

    @pytest.fixture
    def ws_io(self, output_queue, event_loop):
        """Create WebSocketIO instance."""
        return WebSocketIO(
            output_queue=output_queue,
            loop=event_loop,
            pretty=True
        )

    def test_send_event_from_another_thread(self, ws_io, output_queue, event_loop):
        """Test sending events from a separate thread."""
        events_sent = []
        ready = threading.Event()

        async def keep_loop_running():
            """Keep the event loop alive to process queued events."""
            ready.set()
            # Keep loop running for 2 seconds
            await asyncio.sleep(2.0)

        def send_from_thread():
            """Send events from non-event-loop thread."""
            # Wait for loop to be ready
            ready.wait(timeout=1.0)
            for i in range(5):
                ws_io._send_event({
                    "type": "test",
                    "payload": {"index": i}
                })
                events_sent.append(i)
                time.sleep(0.01)  # Small delay

        # Start sender thread
        thread = threading.Thread(target=send_from_thread)
        thread.start()

        # Keep event loop running while thread sends events
        event_loop.run_until_complete(keep_loop_running())

        thread.join(timeout=5.0)

        # Verify all events were sent
        assert len(events_sent) == 5
        assert events_sent == [0, 1, 2, 3, 4]

        # Try to receive events from queue
        received = []
        try:
            while True:
                event = event_loop.run_until_complete(
                    asyncio.wait_for(output_queue.get(), timeout=0.1)
                )
                received.append(event)
                if len(received) >= 5:
                    break
        except asyncio.TimeoutError:
            pass

        # At least some events should have been received
        assert len(received) > 0

    def test_concurrent_input_waits(self, ws_io, event_loop):
        """Test multiple concurrent get_input calls."""
        results = []
        errors = []
        request_ids = []

        def worker(worker_id):
            """Worker that waits for input."""
            try:
                result = ws_io.get_input(f"Worker {worker_id} input")
                results.append((worker_id, result))
            except Exception as e:
                errors.append((worker_id, e))

        # Start multiple workers
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Give threads time to reach wait and send events
        time.sleep(0.2)

        # Collect request_ids from events
        for _ in range(3):
            try:
                event = event_loop.run_until_complete(
                    asyncio.wait_for(ws_io._output_queue.get(), timeout=1.0)
                )
                if event["payload"]["action"] == "request_input":
                    request_ids.append(event["payload"]["data"]["request_id"])
            except asyncio.TimeoutError:
                break

        # Provide inputs to unblock threads (using request_ids)
        for i, request_id in enumerate(request_ids):
            ws_io.receive_input(f"Response {i}", request_id=request_id)

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5.0)

        # Verify results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 3

        # Each worker should have gotten a unique response
        worker_ids = [r[0] for r in results]
        assert sorted(worker_ids) == [0, 1, 2]

    def test_confirm_ask_thread_safety(self, ws_io, event_loop):
        """Test thread-safety of confirm_ask."""
        confirmations = []

        def request_confirmation():
            """Request confirmation from another thread."""
            result = ws_io.confirm_ask(
                question="Do you want to proceed?",
                default="y"
            )
            confirmations.append(result)

        # Start confirmation thread
        thread = threading.Thread(target=request_confirmation)
        thread.start()

        # Wait a bit for the request to be sent
        time.sleep(0.1)

        # Check that confirmation was requested
        event = event_loop.run_until_complete(
            asyncio.wait_for(ws_io._output_queue.get(), timeout=1.0)
        )
        assert event["payload"]["action"] == "confirm_ask"
        confirm_id = event["payload"]["data"]["confirm_id"]

        # Send response
        ws_io.receive_confirm_response(confirm_id, True)

        # Wait for thread to complete
        thread.join(timeout=5.0)

        # Verify result
        assert len(confirmations) == 1
        assert confirmations[0] is True

    def test_tool_output_thread_safety(self, ws_io, output_queue, event_loop):
        """Test tool_output from multiple threads."""
        threads = []
        messages = [
            "Message 1 from thread A",
            "Message 2 from thread B",
            "Message 3 from thread C"
        ]

        def send_tool_output(msg):
            """Send tool output from a thread."""
            ws_io.tool_output(msg, log_only=False)

        # Send from multiple threads
        for msg in messages:
            thread = threading.Thread(target=send_tool_output, args=(msg,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=5.0)

        # Collect events from queue
        events = []
        try:
            for _ in range(len(messages)):
                event = event_loop.run_until_complete(
                    asyncio.wait_for(output_queue.get(), timeout=1.0)
                )
                events.append(event)
        except asyncio.TimeoutError:
            pass

        # All events should have been sent
        assert len(events) == len(messages)

    def test_input_error_handling(self, ws_io, event_loop):
        """Test error propagation through input mechanism."""
        error_received = []
        request_id_collected = []

        def wait_for_input():
            """Wait for input and expect error."""
            try:
                ws_io.get_input("Enter value:")
            except ValueError as e:
                error_received.append(e)

        # Start waiting thread
        thread = threading.Thread(target=wait_for_input)
        thread.start()

        # Wait for request to be sent
        time.sleep(0.1)

        # Get request_id
        try:
            event = event_loop.run_until_complete(
                asyncio.wait_for(ws_io._output_queue.get(), timeout=1.0)
            )
            if event["payload"]["action"] == "request_input":
                request_id = event["payload"]["data"]["request_id"]
                request_id_collected.append(request_id)
        except asyncio.TimeoutError:
            pass

        # Send error
        if request_id_collected:
            test_error = ValueError("Test error")
            ws_io.receive_error(test_error, request_id=request_id_collected[0])

        # Wait for thread
        thread.join(timeout=5.0)

        # Verify error was received
        assert len(error_received) == 1
        assert str(error_received[0]) == "Test error"

    def test_concurrent_confirms(self, ws_io, event_loop):
        """Test multiple concurrent confirmations."""
        results = []

        def request_confirm(question):
            """Request a confirmation."""
            result = ws_io.confirm_ask(question, default="y")
            results.append((question, result))

        # Start multiple confirmation requests
        threads = []
        questions = [
            "Proceed with step 1?",
            "Proceed with step 2?",
            "Proceed with step 3?"
        ]

        for q in questions:
            thread = threading.Thread(target=request_confirm, args=(q,))
            threads.append(thread)
            thread.start()

        # Wait for all requests to be queued
        time.sleep(0.2)

        # Respond to each confirmation
        for i, q in enumerate(questions):
            # Get the confirm_id from the queue
            try:
                event = event_loop.run_until_complete(
                    asyncio.wait_for(ws_io._output_queue.get(), timeout=1.0)
                )
                if event["payload"]["action"] == "confirm_ask":
                    confirm_id = event["payload"]["data"]["confirm_id"]
                    # Respond with alternating yes/no
                    ws_io.receive_confirm_response(confirm_id, i % 2 == 0)
            except asyncio.TimeoutError:
                break

        # Wait for all threads
        for thread in threads:
            thread.join(timeout=10.0)

        # Verify all confirmations completed
        assert len(results) == len(questions)


class TestWebSocketIOIntegration:
    """Integration tests for WebSocketIO."""

    @pytest.fixture
    def event_loop(self):
        """Create event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop
        loop.close()

    def test_full_interaction_flow(self, event_loop):
        """Test complete flow: output -> input -> confirm."""
        output_queue = asyncio.Queue()
        ws_io = WebSocketIO(output_queue, event_loop)

        events = []

        # Simulate Aider thread
        def aider_workflow():
            """Simulate Aider interaction."""
            # Send some output
            ws_io.tool_output("Starting analysis...", log_only=False)

            # Ask for input
            user_input = ws_io.get_input("Please provide file name:")
            ws_io.tool_output(f"Analyzing {user_input}...", log_only=False)

            # Ask for confirmation
            proceed = ws_io.confirm_ask("Apply changes?", default="y")
            ws_io.tool_output(f"Changes {'applied' if proceed else 'rejected'}", log_only=False)

        # Start Aider in thread
        aider_thread = threading.Thread(target=aider_workflow)
        aider_thread.start()

        # Process events
        try:
            while True:
                try:
                    event = event_loop.run_until_complete(
                        asyncio.wait_for(output_queue.get(), timeout=1.0)
                    )
                    events.append(event)

                    # Handle request_input
                    if event["payload"]["action"] == "request_input":
                        request_id = event["payload"]["data"].get("request_id")
                        ws_io.receive_input("test_file.py", request_id=request_id)

                    # Handle confirm_ask
                    elif event["payload"]["action"] == "confirm_ask":
                        confirm_id = event["payload"]["data"]["confirm_id"]
                        ws_io.receive_confirm_response(confirm_id, True)

                    # Stop if we've seen enough
                    if len(events) >= 4:
                        break

                except asyncio.TimeoutError:
                    break

        finally:
            aider_thread.join(timeout=10.0)

        # Verify workflow completed
        assert len(events) >= 4
        actions = [e["payload"]["action"] for e in events]
        assert "log" in actions
        assert "request_input" in actions
        assert "confirm_ask" in actions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
