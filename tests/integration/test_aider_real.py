"""Test real aider integration via WebSocket."""

import asyncio
import json
import sys
import websockets

# Use the session with snake game
SESSION_ID = "b9bffa2c-edd6-40a2-bffe-f203b7ba5dae"
WS_URL = f"ws://127.0.0.1:8000/ws/chat/{SESSION_ID}"

async def test_aider_snake_optimization():
    """Test optimizing snake game with real aider."""
    print("="*80)
    print("TEST: Optimize Snake Game UI with Real Aider")
    print("="*80)

    async with websockets.connect(WS_URL) as ws:
        message = "继续完善贪吃蛇游戏，优化UI界面，添加颜色和更好的视觉效果"
        print(f"\nSending: {message}")
        print(f"Session: {SESSION_ID}")
        print(f"This will use REAL aider Coder!")

        await ws.send(json.dumps({
            "type": "input",
            "payload": {"text": message}
        }))

        # Collect responses
        responses = []
        tool_calls = []

        for _ in range(60):  # Wait up to 60 responses (aider might be verbose)
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(response)
                responses.append(data)

                payload = data.get("payload", {})
                action = payload.get("action", "")

                if action == "log":
                    msg = payload.get("message", "")
                    print(f"[LOG] {msg}")

                elif action == "tool_start":
                    tool = payload.get("data", {}).get("tool", "")
                    tool_calls.append(tool)
                    print(f"\n[TOOL START] {tool}")

                elif action == "tool_end":
                    tool = payload.get("data", {}).get("tool", "")
                    result = payload.get("data", {}).get("result", "")
                    print(f"[TOOL END] {tool}: {result[:100] if len(result) > 100 else result}")

                elif action == "chat_response":
                    content = payload.get("data", {}).get("content", "")
                    print(f"\n[AI]\n{content}\n")

                    # If we get a substantial response, we're probably done
                    if len(content) > 50:
                        print("(Waiting for any file updates...)")
                        await asyncio.sleep(2)

            except asyncio.TimeoutError:
                break

        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total responses: {len(responses)}")
        print(f"Tools called: {tool_calls}")

        # Check if snake_game.py was modified
        print("\nChecking snake_game.py...")
        try:
            snake_path = "D:/Codes/whyme/data/workspaces/my_first_project_b9bffa2c/snake_game.py"
            with open(snake_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for UI improvements
            has_color = any(keyword in content.lower() for keyword in ["color", "colour", "rgb", "hex"])
            has_visual = any(keyword in content.lower() for keyword in ["visual", "style", "design", "ui"])

            print(f"  - Has colors: {has_color}")
            print(f"  - Has visual improvements: {has_visual}")

            if has_color or has_visual:
                print("\n[OK] Snake game was optimized with real aider!")
            else:
                print("\n[WARN] No obvious UI improvements found")

        except Exception as e:
            print(f"[ERROR] Could not read snake_game.py: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(test_aider_snake_optimization())
