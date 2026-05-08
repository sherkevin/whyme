"""Test guess_number.py modification."""

import asyncio
import json
import sys

import websockets

SESSION_ID = "f99eedc7-7016-404f-9166-08d0087f162f"
WS_URL = f"ws://127.0.0.1:8000/ws/chat/{SESSION_ID}"

async def test_modify_guess_game():
    """Test modifying guess_number.py"""
    print("="*80)
    print("TEST: Modify guess_number.py to add 7-attempt limit")
    print("="*80)

    async with websockets.connect(WS_URL) as ws:
        message = "修改guess_number.py，增加猜测次数限制功能，玩家只能猜7次，如果用完次数则提示游戏失败并显示正确答案"
        print(f"\nSending: {message}")

        await ws.send(json.dumps({
            "type": "input",
            "payload": {"text": message}
        }))

        # Collect responses
        for _ in range(30):
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(response)

                payload = data.get("payload", {})
                action = payload.get("action", "")

                if action == "tool_start":
                    print(f"\n[TOOL START] {payload.get('data', {})}")
                elif action == "tool_end":
                    print(f"[TOOL END] {payload.get('data', {})}")
                elif action == "chat_response":
                    content = payload.get("data", {}).get("content", "")
                    print(f"\n[AI RESPONSE] {content[:300]}")

            except TimeoutError:
                break

        # Verify file content
        print("\n" + "="*80)
        print("Verifying guess_number.py content...")
        print("="*80)
        with open("D:/Codes/whyme/data/workspaces/test-python-app/guess_number.py", encoding="utf-8") as f:
            content = f.read()

        # Check for key features
        has_max_attempts = "max_attempts" in content or "MAX_ATTEMPTS" in content
        has_7 = "7" in content
        has_fail_message = any(keyword in content for keyword in ["失败", "fail", "超过", "exceed"])

        print("\nFeatures found:")
        print(f"  - max_attempts constant: {has_max_attempts}")
        print(f"  - Number 7: {has_7}")
        print(f"  - Failure message: {has_fail_message}")

        if has_max_attempts or has_7:
            print("\n✓ SUCCESS: File was modified with attempt limit!")
            # Show relevant lines
            lines = content.split('\n')
            for i, line in enumerate(lines[:40], 1):  # Show first 40 lines
                if any(keyword in line for keyword in ["max_attempts", "MAX_ATTEMPTS", "attempts", "7", "次"]):
                    print(f"  Line {i}: {line}")
        else:
            print("\n✗ FAILED: File was NOT modified properly")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(test_modify_guess_game())
