"""Quick WebSocket test to verify aider works through web UI."""

import asyncio
import websockets
import json

async def test_websocket():
    """Test WebSocket with simple file creation."""
    session_id = "b9bffa2c-edd6-40a2-bffe-f203b7ba5dae"
    uri = f"ws://127.0.0.1:8000/ws/chat/{session_id}"

    print("="*80)
    print("WebSocket Test - Creating test.txt")
    print("="*80)

    try:
        async with websockets.connect(uri) as ws:
            print("[OK] Connected to WebSocket")

            # Send a simple message
            message = {
                "type": "input",
                "payload": {
                    "text": "Create a file test.txt with content: Hello from Aider Web UI!"
                }
            }

            print("[OK] Sending message...")
            await ws.send(json.dumps(message))

            # Receive responses
            response_count = 0
            while response_count < 10:  # Max 10 messages
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=30.0)
                    data = json.loads(response)
                    response_count += 1

                    print(f"[OK] Received [{response_count}]: {data['type']}")

                    if data.get('type') == 'done':
                        print("[OK] Done signal received")
                        break

                    if 'payload' in data and isinstance(data['payload'], dict):
                        payload = data['payload']
                        if 'content' in payload:
                            content = payload['content']
                            # Check for success indicators
                            if 'Applied edit' in content or 'Added' in content:
                                print(f"[OK] File edit detected!")
                            if 'Error' not in content and len(content) > 50:
                                print(f"[OK] Received content ({len(content)} chars)")

                except asyncio.TimeoutError:
                    print("[OK] Timeout (waiting for more responses)")
                    break

            print(f"\n[OK] Total responses: {response_count}")

    except Exception as e:
        print(f"[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Check if file was created
    from pathlib import Path
    test_file = Path("data/workspaces/my_first_project_b9bffa2c/test.txt")
    if test_file.exists():
        print(f"\n[SUCCESS] File created: {test_file}")
        print(f"   Content: {test_file.read_text(encoding='utf-8')}")
        return True
    else:
        print(f"\n[FAIL] File not created: {test_file}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_websocket())
    print("\n" + "="*80)
    if result:
        print("FINAL RESULT: [SUCCESS] ALL TESTS PASSED")
        print("The system is ready for use!")
    else:
        print("FINAL RESULT: [FAIL] TEST FAILED")
    print("="*80)
