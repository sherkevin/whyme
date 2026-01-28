"""Detailed WebSocket test to see what's happening."""

import asyncio
import websockets
import json
from pathlib import Path

async def test_detailed():
    """Test WebSocket with detailed output."""
    session_id = "b9bffa2c-edd6-40a2-bffe-f203b7ba5dae"
    uri = f"ws://127.0.0.1:8000/ws/chat/{session_id}"

    print("="*80)
    print("DETAILED WebSocket Test")
    print("="*80)

    try:
        async with websockets.connect(uri) as ws:
            print("Connected")

            message = {
                "type": "input",
                "payload": {
                    "text": "Create a file hello_ws.txt with content: Hello from WebSocket!"
                }
            }

            print(f"Sending: {message['payload']['text']}")
            await ws.send(json.dumps(message))

            # Receive all responses
            all_responses = []
            for _ in range(50):  # Max 50 messages
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=30.0)  # Increased timeout
                    data = json.loads(response)
                    all_responses.append(data)

                    print(f"\n--- Response {len(all_responses)} ---")
                    print(f"Type: {data.get('type')}")

                    if 'payload' in data:
                        payload = data['payload']
                        if isinstance(payload, dict):
                            for key, value in payload.items():
                                if key == 'data' and isinstance(value, dict):
                                    print(f"  {key}:")
                                    for k, v in value.items():
                                        if k == 'content':
                                            print(f"    {k}: {v[:100]}...")
                                        else:
                                            print(f"    {k}: {v}")
                                elif isinstance(value, str) and len(value) > 100:
                                    print(f"  {key}: {value[:100]}...")
                                else:
                                    print(f"  {key}: {value}")

                    if data.get('type') == 'done':
                        break

                except asyncio.TimeoutError:
                    print("\nTimeout - no more responses")
                    break

            print(f"\nTotal responses: {len(all_responses)}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return

    # Check workspace
    workspace = Path("data/workspaces/my_first_project_b9bffa2c")
    print(f"\nWorkspace contents:")
    if workspace.exists():
        for f in workspace.iterdir():
            if f.is_file():
                print(f"  - {f.name}: {f.stat().st_size} bytes")
                if f.suffix == '.txt' and f.stat().st_size < 200:
                    print(f"    Content: {f.read_text(encoding='utf-8')}")
    else:
        print("  Workspace does not exist")

if __name__ == "__main__":
    asyncio.run(test_detailed())
