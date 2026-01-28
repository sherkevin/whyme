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
from typing import Any, Optional

from agent_os.capabilities.coding._vendor.aider_io import InputOutput


class WebSocketIO(InputOutput):
    """Thread-safe WebSocket IO adapter for Aider.

    This class allows Aider (running in a separate thread) to communicate
    with a FastAPI WebSocket (running in the asyncio event loop).

    Usage:
        # In FastAPI WebSocket handler:
        queue = asyncio.Queue()
        ws_io = WebSocketIO(queue, loop=asyncio.get_running_loop())

        # Run Aider in separate thread:
        thread = threading.Thread(target=lambda: aider.run(io=ws_io))
        thread.start()

        # In WebSocket receive loop:
        msg = await websocket.receive_text()
        ws_io.receive_input(msg)  # Unblock Aider's get_input()

        # Consume output from queue:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
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

        # Thread-safe synchronization for user input
        self._input_event = threading.Event()
        self._input_lock = threading.Lock()
        self._input_buffer: Optional[str] = None
        self._input_error: Optional[Exception] = None

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

            # Wait for it to complete (with shorter timeout for faster response)
            future.result(timeout=1.0)
        except asyncio.TimeoutError:
            # Event loop is busy - log and continue
            print(f"[WebSocketIO] Event loop timeout when sending event")
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

        Thread-safe: Uses threading.Event and Lock to coordinate between
        the executor thread (this method) and the event loop thread
        (receive_input method).
        """
        # Send request for input
        self._send_event({
            "type": "event",
            "payload": {
                "action": "request_input",
                "data": {"prompt": prompt_text},
                "status": "waiting_for_user"
            }
        })

        # Wait for input (blocking in executor thread)
        # Use timeout to prevent deadlocks during shutdown
        if not self._input_event.wait(timeout=300):  # 5 minute timeout
            raise TimeoutError("Timeout waiting for user input")

        # Acquire lock to read input safely
        with self._input_lock:
            if self._input_error is not None:
                error = self._input_error
                self._input_error = None
                raise error

            result = self._input_buffer or ""

            # Clear state for next input
            self._input_buffer = None
            self._input_event.clear()

        return result

    def receive_input(self, text: str) -> None:
        """Receive user input from WebSocket (called from event loop).

        This unblocks the get_input() method waiting in the executor thread.

        Thread-safe: Uses threading.Lock to coordinate access to shared state.
        """
        with self._input_lock:
            self._input_buffer = text
            self._input_error = None
            self._input_event.set()

    def receive_error(self, error: Exception) -> None:
        """Send an error to waiting get_input() (called from event loop).

        This allows the event loop to signal an error to the executor thread.
        """
        with self._input_lock:
            self._input_error = error
            self._input_event.set()

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
