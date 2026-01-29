"""Simplified WebSocketIO thread safety test."""

import asyncio
import threading
import time
from typing import Any

from agent_os.server.websocket_io import WebSocketIO


def test_simple_concurrent_input():
    """Simple test for concurrent input handling."""
    print("=== Testing WebSocketIO Thread Safety ===")

    # Create event loop and run in background thread
    loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()

    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()

    time.sleep(0.1)  # Let loop start

    try:
        # Create WebSocketIO
        output_queue = asyncio.Queue()
        ws_io = WebSocketIO(output_queue, loop)

        # Test 1: Single input
        print("\n[Test 1] Single input request")

        def single_input_thread():
            result = ws_io.get_input("Enter value:")
            print(f"  Received: {result}")
            return result

        thread1 = threading.Thread(target=single_input_thread)
        thread1.start()

        # Wait for request
        time.sleep(0.2)
        future = asyncio.run_coroutine_threadsafe(output_queue.get(), loop)
        event = future.result(timeout=2)
        request_id = event["payload"]["data"]["request_id"]

        # Send response
        ws_io.receive_input("test_value", request_id=request_id)
        thread1.join(timeout=5)
        print("  [OK] Single input test passed")

        # Test 2: Concurrent inputs
        print("\n[Test 2] Concurrent input requests")

        results = []
        def worker(worker_id):
            try:
                result = ws_io.get_input(f"Worker {worker_id}")
                results.append((worker_id, result))
                print(f"  Worker {worker_id} got: {result}")
            except Exception as e:
                print(f"  Worker {worker_id} error: {e}")

        # Start 3 workers
        threads = []
        for i in range(3):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all requests and collect IDs
        time.sleep(0.3)
        request_ids = []

        for _ in range(3):
            try:
                future = asyncio.run_coroutine_threadsafe(output_queue.get(), loop)
                event = future.result(timeout=2)

                if event["payload"]["action"] == "request_input":
                    request_ids.append(event["payload"]["data"]["request_id"])
            except Exception as e:
                print(f"  Error getting event: {e}")
                break

        # Respond to each request
        for i, req_id in enumerate(request_ids):
            ws_io.receive_input(f"Response{i}", request_id=req_id)

        # Wait for all workers
        for t in threads:
            t.join(timeout=5)

        print(f"  [OK] {len(results)} workers completed")

        # Verify
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        worker_ids = [r[0] for r in results]
        assert sorted(worker_ids) == [0, 1, 2]
        print("  [OK] All workers got unique responses")

        print("\n=== All tests passed ===")

    finally:
        # Clean up
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join(timeout=2)
        loop.close()


if __name__ == "__main__":
    test_simple_concurrent_input()
