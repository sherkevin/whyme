"""Simple WebSocket test to verify aider works."""

import asyncio
import json
from pathlib import Path

import websockets


async def quick_test():
    """Quick test: create a file via WebSocket."""
    uri = "ws://127.0.0.1:8000/ws/chat/b9bffa2c-edd6-40a2-bffe-f203b7ba5dae"

    try:
        async with websockets.connect(uri) as ws:
            print("[OK] Connected")

            # Send message
            msg = {
                "type": "input",
                "payload": {"text": "Create file websocket_test.txt with: WebSocket Success!"}
            }

            await ws.send(json.dumps(msg))
            print("[OK] Message sent")

            # Wait for responses
            for i in range(60):  # Wait up to 2 minutes (60 * 2s)
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=60.0)
                    data = json.loads(response)

                    if data.get('type') == 'event':
                        payload = data.get('payload', {})
                        action = payload.get('action', '')

                        if action == 'chat_response':
                            content = payload.get('data', {}).get('content', '')
                            print(f"\n[RESPONSE] Received ({len(content)} chars)")

                            if 'Error' in content:
                                print(f"[ERROR] {content[:200]}")
                                return False
                            elif 'websocket_test.txt' in content or 'WebSocket Success' in content:
                                print("[OK] Response looks good!")

                        if action == 'done':
                            print("[OK] Done")
                            break

                except TimeoutError:
                    print(f"[WAIT] Waiting... ({i*2}s)")
                    continue

            # Check file
            print("\n[CHECK] Looking for file...")
            test_file = Path("data/workspaces/my_first_project_b9bffa2c/websocket_test.txt")

            if test_file.exists():
                content = test_file.read_text(encoding='utf-8')
                print("\n[SUCCESS] File created!")
                print(f"Location: {test_file}")
                print(f"Content: {content}")
                return True
            else:
                print(f"\n[FAIL] File not found at {test_file}")

                # Check if file was created elsewhere
                print("\n[SEARCH] Searching for file...")
                import os
                for root, dirs, files in os.walk("."):
                    if "websocket_test.txt" in files:
                        found = Path(root) / "websocket_test.txt"
                        print(f"Found at: {found}")
                        print(f"Content: {found.read_text(encoding='utf-8')}")
                        return False

                return False

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(quick_test())
    print("\n" + "="*80)
    if result:
        print("FINAL: WEBSOCKET INTEGRATION WORKS!")
    else:
        print("FINAL: NEEDS MORE WORK")
    print("="*80)
