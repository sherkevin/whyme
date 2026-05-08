"""Extended test for real aider integration."""

import asyncio
import json
import sys

import websockets

SESSION_ID = "b9bffa2c-edd6-40a2-bffe-f203b7ba5dae"
WS_URL = f"ws://127.0.0.1:8000/ws/chat/{SESSION_ID}"

async def test_aider_extended():
    """Test with longer timeout."""
    print("="*80)
    print("EXTENDED TEST: Real Aider Integration")
    print("="*80)

    async with websockets.connect(WS_URL) as ws:
        message = "优化贪吃蛇游戏的UI，添加彩色界面"
        print(f"\nSending: {message}")

        await ws.send(json.dumps({
            "type": "input",
            "payload": {"text": message}
        }))

        # Wait longer for responses
        for i in range(120):  # 2 minutes
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(response)

                payload = data.get("payload", {})
                action = payload.get("action", "")

                if action == "log":
                    msg = payload.get("message", "")
                    print(f"[{i:02d}] [LOG] {msg}")

                elif action == "chat_response":
                    content = payload.get("data", {}).get("content", "")
                    if content:
                        print(f"\n[{i:02d}] [AI RESPONSE]\n{content}\n")
                    else:
                        print(f"[{i:02d}] [Empty AI response]")

            except TimeoutError:
                continue

        print("\n[Test ended - timeout or connection closed]")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(test_aider_extended())
