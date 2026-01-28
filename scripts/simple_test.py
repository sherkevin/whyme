"""Simple test to check AI tool calling behavior."""

import asyncio
import json
import sys
import websockets

SESSION_ID = "f99eedc7-7016-404f-9166-08d0087f162f"
WS_URL = f"ws://127.0.0.1:8000/ws/chat/{SESSION_ID}"

async def test_simple_write():
    """Test simple file writing"""
    print("="*80)
    print("TEST: Simple File Write")
    print("="*80)

    async with websockets.connect(WS_URL) as ws:
        # Send a simple write request
        message = "创建一个文件test.txt，内容是'Test content'"
        print(f"\nSending: {message}")

        await ws.send(json.dumps({
            "type": "input",
            "payload": {"text": message}
        }))

        # Collect all responses
        all_responses = []
        for _ in range(20):  # Wait for up to 20 responses
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(response)
                all_responses.append(data)

                payload = data.get("payload", {})
                action = payload.get("action", "")

                if action == "tool_start":
                    print(f"\n[TOOL START] {payload.get('data', {})}")
                elif action == "tool_end":
                    print(f"[TOOL END] {payload.get('data', {})}")
                elif action == "chat_response":
                    print(f"\n[RESPONSE] {payload.get('data', {}).get('content', '')[:200]}")
                elif action == "log":
                    print(f"[LOG] {payload.get('message', '')}")

            except asyncio.TimeoutError:
                break

        print(f"\nTotal responses: {len(all_responses)}")

async def test_read_and_modify():
    """Test reading and modifying a file"""
    print("\n" + "="*80)
    print("TEST: Read and Modify File")
    print("="*80)

    async with websockets.connect(WS_URL) as ws:
        # First, read a file
        message = "请先读取hello.txt的内容，然后在文件末尾加上' - MODIFIED'"
        print(f"\nSending: {message}")

        await ws.send(json.dumps({
            "type": "input",
            "payload": {"text": message}
        }))

        # Collect all responses
        tool_calls = []
        for _ in range(30):
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(response)

                payload = data.get("payload", {})
                action = payload.get("action", "")

                if action == "tool_start":
                    tool = payload.get("data", {}).get("tool", "")
                    tool_calls.append(("start", tool))
                    print(f"\n[TOOL START] {tool}")

                elif action == "tool_end":
                    tool = payload.get("data", {}).get("tool", "")
                    result = payload.get("data", {}).get("result", "")
                    tool_calls.append(("end", tool))
                    print(f"[TOOL END] {tool}: {result[:100]}")

                elif action == "chat_response":
                    content = payload.get("data", {}).get("content", "")
                    print(f"\n[AI RESPONSE] {content[:200]}")

                elif action == "log":
                    print(f"[LOG] {payload.get('message', '')}")

            except asyncio.TimeoutError:
                break

        print(f"\n\nTool calls made: {[t for t, _ in tool_calls]}")

        # Verify file content
        try:
            with open("D:/Codes/whyme/data/workspaces/test-python-app/hello.txt", "r") as f:
                content = f.read()
                print(f"\nActual file content: '{content}'")
                if "MODIFIED" in content:
                    print("SUCCESS: File was modified!")
                else:
                    print("FAILED: File was NOT modified")
        except Exception as e:
            print(f"Error reading file: {e}")

async def main():
    await test_simple_write()
    await asyncio.sleep(2)
    await test_read_and_modify()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())
