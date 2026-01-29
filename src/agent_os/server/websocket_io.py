"""WebSocketIO - Thread-safe IO adapter for Aider.

This module provides a thread-safe InputOutput implementation that bridges
Aider's synchronous interface with FastAPI's asynchronous WebSocket.

Design Principles:
1. Aider runs in a separate thread (executor thread)
2. FastAPI runs in the main asyncio event loop
3. Communication happens via thread-safe queues and events
4. All event loop interactions use run_coroutine_threadsafe
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from typing import Any, Optional

from agent_os.capabilities.coding._vendor.aider_io import InputOutput


class WebSocketIO(InputOutput):
    """Thread-safe WebSocket IO adapter for Aider.

    This class allows Aider (running in a separate thread) to communicate
    with a FastAPI WebSocket (running in the asyncio event loop).

    Thread-safety is achieved using:
    - Per-request IDs to match requests with responses
    - Thread-safe dict for pending requests
    - Threading.Events for signaling
    """

    def __init__(
        self,
        output_queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
        pretty: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize WebSocketIO.

        Args:
            output_queue: asyncio.Queue for sending events to FastAPI
            loop: The asyncio event loop (must be the running loop)
            pretty: Whether to format output nicely
            **kwargs: Additional arguments passed to InputOutput
        """
        super().__init__(pretty=pretty, **kwargs)

        self._output_queue = output_queue
        self._loop = loop

        # Thread-safe storage for pending input requests
        # Key: request_id, Value: dict with 'event', 'result', 'error'
        self._pending_requests: dict[str, dict[str, Any]] = {}
        self._requests_lock = threading.Lock()

        # Track which thread we're in (for debugging)
        self._creator_thread = threading.current_thread()

    def _send_event(self, event: dict[str, Any]) -> None:
        """Send an event to the output queue (thread-safe).

        This is called from the Aider thread (executor thread).
        """
        try:
            async def _put() -> None:
                await self._output_queue.put(event)

            # Schedule the coroutine in the event loop
            future = asyncio.run_coroutine_threadsafe(_put(), self._loop)

            # Wait for it to complete with reasonable timeout
            # Increased timeout to handle busy event loops
            future.result(timeout=5.0)
        except asyncio.TimeoutError:
            # Event loop is busy - log and continue
            print(f"[WebSocketIO] Warning: Event loop timeout when sending event")
            # Don't fail - the event might still be queued
        except Exception as e:
            # If we can't send to the queue, log it but don't crash
            print(f"[WebSocketIO] Failed to send event: {e}")

    def tool_output(self, msg: str, log_only: bool = False) -> None:
        """Send tool output to WebSocket.

        Called by Aider from the executor thread.
        """
        if not log_only:
            self._send_event({
                "type": "event",
                "payload": {
                    "action": "log",
                    "message": msg,
                    "status": "executing"
                }
            })

    def get_input(self, prompt_text: str, *args: Any, **kwargs: Any) -> str:
        """Get user input from WebSocket.

        This is a synchronous method (called by Aider from executor thread)
        that blocks until input arrives via receive_input().

        Thread-safe: Uses request IDs to match requests with responses.
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Create event for this request
        input_event = threading.Event()
        request_data = {
            "event": input_event,
            "result": None,
            "error": None
        }

        # Register this request
        with self._requests_lock:
            self._pending_requests[request_id] = request_data

        # Send request for input
        self._send_event({
            "type": "event",
            "payload": {
                "action": "request_input",
                "data": {
                    "request_id": request_id,
                    "prompt": prompt_text
                },
                "status": "waiting_for_user"
            }
        })

        # Wait for response (blocking in executor thread)
        if not input_event.wait(timeout=300):  # 5 minute timeout
            # Clean up on timeout
            with self._requests_lock:
                self._pending_requests.pop(request_id, None)
            raise TimeoutError("Timeout waiting for user input")

        # Get the result
        result = request_data["result"]
        error = request_data["error"]

        # Clean up
        with self._requests_lock:
            self._pending_requests.pop(request_id, None)

        # Check for error
        if error is not None:
            raise error

        return result or ""

    def receive_input(self, text: str, request_id: str | None = None) -> None:
        """Receive user input from WebSocket (called from event loop).

        This unblocks a waiting get_input() method.

        Args:
            text: The user's input text
            request_id: Optional request ID to respond to (oldest if None)
        """
        with self._requests_lock:
            # If no request_id provided, use the oldest one
            if request_id is None:
                if not self._pending_requests:
                    print("[WebSocketIO] Warning: receive_input called with no pending requests")
                    return
                # Get the first (oldest) request
                request_id = next(iter(self._pending_requests))

            # Find and fulfill the request
            if request_id in self._pending_requests:
                request_data = self._pending_requests[request_id]
                request_data["result"] = text
                request_data["error"] = None
                request_data["event"].set()
            else:
                print(f"[WebSocketIO] Warning: Unknown request_id: {request_id}")

    def receive_error(self, error: Exception, request_id: str | None = None) -> None:
        """Send an error to waiting get_input() (called from event loop).

        Args:
            error: The exception to raise
            request_id: Optional request ID to respond to (oldest if None)
        """
        with self._requests_lock:
            # If no request_id provided, use the oldest one
            if request_id is None:
                if not self._pending_requests:
                    print(f"[WebSocketIO] Warning: receive_error called with no pending requests: {error}")
                    return
                request_id = next(iter(self._pending_requests))

            # Find and fulfill the request with error
            if request_id in self._pending_requests:
                request_data = self._pending_requests[request_id]
                request_data["result"] = None
                request_data["error"] = error
                request_data["event"].set()
            else:
                print(f"[WebSocketIO] Warning: Unknown request_id in receive_error: {request_id}")

    def confirm_ask(
        self,
        question: str,
        default: str = "y",
        subject: str = "",
        explicit_yes: bool = False,
    ) -> bool:
        """Ask user a yes/no question via WebSocket.

        This sends a confirmation request and blocks until the user responds.

        Thread-safe: Uses threading.Event to wait for response from event loop.
        """
        # Create unique confirmation ID
        import uuid
        confirm_id = str(uuid.uuid4())

        # Create event and result storage for this confirmation
        confirm_event = threading.Event()
        result_storage = {"response": None}

        # Store in a dictionary that receive_confirm_response can access
        if not hasattr(self, "_pending_confirmations"):
            self._pending_confirmations = {}
        self._pending_confirmations[confirm_id] = {
            "event": confirm_event,
            "result": result_storage
        }

        # Send confirmation request
        self._send_event({
            "type": "event",
            "payload": {
                "action": "confirm_ask",
                "data": {
                    "confirm_id": confirm_id,
                    "question": question,
                    "default": default,
                    "subject": subject,
                    "explicit_yes": explicit_yes
                },
                "status": "waiting_for_user"
            }
        })

        # Wait for user response (with timeout to prevent deadlocks)
        # Use timeout to prevent indefinite blocking during shutdown
        if not confirm_event.wait(timeout=300):  # 5 minute timeout
            # Clean up
            if confirm_id in self._pending_confirmations:
                del self._pending_confirmations[confirm_id]
            raise TimeoutError(f"Timeout waiting for user confirmation: {question}")

        # Get the result
        response = result_storage.get("response", default)

        # Clean up
        if confirm_id in self._pending_confirmations:
            del self._pending_confirmations[confirm_id]

        # Parse response
        if isinstance(response, bool):
            return response
        elif isinstance(response, str):
            return response.lower() in ("y", "yes", "true", "1", "approve")
        else:
            # Fallback to default
            return default == "y" or default == "yes"

    def receive_confirm_response(self, confirm_id: str, response: bool | str) -> None:
        """Receive confirmation response from WebSocket (called from event loop).

        This unblocks the confirm_ask() method waiting in the executor thread.

        Args:
            confirm_id: The confirmation ID to respond to
            response: The user's response (True/False or "yes"/"no")
        """
        if not hasattr(self, "_pending_confirmations"):
            return

        if confirm_id in self._pending_confirmations:
            confirmation = self._pending_confirmations[confirm_id]
            confirmation["result"]["response"] = response
            confirmation["event"].set()

    def prompt_ask(self, prompt: str, default: str = "") -> str:
        """Ask user for text input (alternative to get_input).

        Delegates to get_input for consistency.
        """
        return self.get_input(prompt)

    def request_diff_confirmation(
        self,
        file_path: str,
        original_content: str,
        modified_content: str,
        description: str = ""
    ) -> bool:
        """Request user confirmation for a file diff.

        This sends a diff to the frontend and blocks until the user approves or rejects.

        Args:
            file_path: Path to the file being modified
            original_content: Original file content
            modified_content: Proposed new content
            description: Description of the changes

        Returns:
            True if user approved, False if rejected
        """
        import uuid
        import difflib

        # Generate unique diff ID
        diff_id = str(uuid.uuid4())

        # Create unified diff
        diff = list(difflib.unified_diff(
            original_content.splitlines(keepends=True),
            modified_content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm=""
        ))

        diff_text = "".join(diff)

        # Create event and result storage for this diff confirmation
        diff_event = threading.Event()
        result_storage = {"approved": None}

        # Store in a dictionary that receive_diff_response can access
        if not hasattr(self, "_pending_diffs"):
            self._pending_diffs = {}
        self._pending_diffs[diff_id] = {
            "event": diff_event,
            "result": result_storage,
            "file_path": file_path,
            "modified_content": modified_content  # Store for later application
        }

        # Send diff confirmation request
        self._send_event({
            "type": "event",
            "payload": {
                "action": "request_diff_confirmation",
                "data": {
                    "diff_id": diff_id,
                    "file_path": file_path,
                    "diff": diff_text,
                    "description": description
                },
                "status": "waiting_for_user"
            }
        })

        # Wait for user response (with timeout)
        if not diff_event.wait(timeout=300):  # 5 minute timeout
            # Clean up on timeout
            if diff_id in self._pending_diffs:
                del self._pending_diffs[diff_id]
            raise TimeoutError(f"Timeout waiting for diff confirmation: {file_path}")

        # Get the result
        approved = result_storage.get("approved", False)

        # Clean up but keep modified_content for application if approved
        if diff_id in self._pending_diffs:
            # If approved, keep it for get_diff_content to retrieve
            if not approved:
                del self._pending_diffs[diff_id]
            else:
                # Mark as approved but keep for content retrieval
                self._pending_diffs[diff_id]["approved"] = True

        return approved

    def receive_diff_response(self, diff_id: str, approved: bool) -> None:
        """Receive diff confirmation response from WebSocket (called from event loop).

        This unblocks the request_diff_confirmation() method waiting in the executor thread.

        Args:
            diff_id: The diff confirmation ID to respond to
            approved: Whether the user approved (True) or rejected (False)
        """
        if not hasattr(self, "_pending_diffs"):
            return

        if diff_id in self._pending_diffs:
            diff_request = self._pending_diffs[diff_id]
            diff_request["result"]["approved"] = approved
            diff_request["event"].set()

    def get_diff_content(self, diff_id: str) -> str | None:
        """Get the modified content for an approved diff.

        This should be called after user approval to retrieve the content to apply.

        Args:
            diff_id: The diff ID to get content for

        Returns:
            The modified content, or None if diff_id not found
        """
        if not hasattr(self, "_pending_diffs"):
            return None

        if diff_id in self._pending_diffs:
            return self._pending_diffs[diff_id].get("modified_content")

        return None

    def clear_diff(self, diff_id: str) -> None:
        """Clean up a diff request after applying changes.

        Args:
            diff_id: The diff ID to clean up
        """
        if hasattr(self, "_pending_diffs") and diff_id in self._pending_diffs:
            del self._pending_diffs[diff_id]


class AiderExecutor:
    """Manages running Aider in a separate thread with WebSocketIO.

    This class handles the lifecycle of running Aider code operations
    in a background thread while communicating via WebSocket.

    Usage:
        executor = AiderExecutor(sandbox, output_queue, loop)
        await executor.start()

        # Later, when Aider needs to do something:
        result = await executor.run_aider_command(lambda io: ...)

        # When done:
        await executor.stop()
    """

    def __init__(
        self,
        sandbox: Any,
        output_queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Initialize the executor.

        Args:
            sandbox: The sandbox instance (ExecutionEnvironment)
            output_queue: Queue for WebSocket events
            loop: The asyncio event loop
        """
        self.sandbox = sandbox
        self._output_queue = output_queue
        self._loop = loop
        self._ws_io: Optional[WebSocketIO] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()

    @property
    def ws_io(self) -> WebSocketIO:
        """Get the WebSocketIO instance (creates if needed)."""
        if self._ws_io is None:
            self._ws_io = WebSocketIO(
                self._output_queue,
                self._loop,
                pretty=True
            )
        return self._ws_io

    def _run_aider_in_thread(self, target: callable) -> None:
        """Run Aider in a separate thread."""
        try:
            self._ready_event.set()
            target(self.ws_io)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.ws_io._send_event({
                "type": "error",
                "payload": {
                    "message": f"Aider error: {str(e)}",
                    "detail": traceback.format_exc()
                }
            })

    async def start(self) -> None:
        """Start the Aider executor thread."""
        if self._thread is not None:
            return  # Already started

        # Thread will be started when needed
        pass

    async def stop(self) -> None:
        """Stop the Aider executor thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def receive_input(self, text: str) -> None:
        """Forward user input to WebSocketIO."""
        if self._ws_io:
            self._ws_io.receive_input(text)
