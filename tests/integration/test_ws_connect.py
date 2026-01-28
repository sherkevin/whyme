"""Test WebSocket connection"""
import asyncio
import websockets
import json

async def test_connection():
    uri = "ws://127.0.0.1:8000/ws/chat/b9bffa2c-edd6-40a2-bffe-f203b7ba5dae"

    try:
        print("Connecting to WebSocket...")
        async with websockets.connect(uri) as ws:
            print("[OK] Connected!")

            # Wait for initial message
            response = await ws.recv()
            data = json.loads(response)
            print(f"[OK] Received: {data}")

            return True
    except Exception as e:
        print(f"[FAIL] Error: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_connection())
