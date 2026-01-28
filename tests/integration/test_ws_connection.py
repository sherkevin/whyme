"""Simple WebSocket connection test"""
import asyncio
import websockets

async def test_ws():
    uri = "ws://127.0.0.1:8003/ws/chat/b9bffa2c-edd6-40a2-bffe-f203b7ba5dae"
    try:
        print("Connecting to", uri, "...")
        async with websockets.connect(uri) as ws:
            print("[OK] Connected!")
            # Wait for initial message
            msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
            print("Received:", msg[:100])
    except Exception as e:
        print("[FAIL] Error:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ws())
