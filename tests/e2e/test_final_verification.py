"""Final verification test for aider integration."""

import asyncio
import json
from pathlib import Path

import websockets


async def test_aider_integration():
    """Test the complete aider integration through WebSocket."""
    session_id = "b9bffa2c-edd6-40a2-bffe-f203b7ba5dae"
    uri = f"ws://127.0.0.1:8000/ws/chat/{session_id}"

    print("="*80)
    print("FINAL VERIFICATION TEST")
    print("="*80)

    try:
        async with websockets.connect(uri) as ws:
            print("[OK] Connected to WebSocket\n")

            # Test 1: Create a simple file
            print("TEST 1: Creating test_simple.txt")
            print("-" * 80)

            message1 = {
                "type": "input",
                "payload": {
                    "text": "Create a file test_simple.txt with: Hello from Aider!"
                }
            }

            await ws.send(json.dumps(message1))
            print("[SENT] Message sent\n")

            # Wait for response
            responses_1 = []
            for i in range(50):
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(response)
                    responses_1.append(data)

                    if data.get('type') == 'event':
                        payload = data.get('payload', {})
                        action = payload.get('action', '')

                        if action == 'chat_response':
                            content = payload.get('data', {}).get('content', '')
                            print(f"[RECEIVED] Chat response ({len(content)} chars)")
                            if 'Error' not in content and len(content) > 20:
                                print("[OK] Got valid response")
                                if 'Hello from Aider' in content or 'test_simple.txt' in content:
                                    print("[OK] Response mentions the file")
                            elif 'Error' in content:
                                print(f"[ERROR] {content[:100]}")

                    if data.get('type') == 'done':
                        print("[OK] Done signal received")
                        break

                except TimeoutError:
                    break

            # Wait a bit for file operations
            await asyncio.sleep(2)

            # Check if file was created
            test_file = Path("data/workspaces/my_first_project_b9bffa2c/test_simple.txt")
            if test_file.exists():
                print(f"\n[SUCCESS] File created: {test_file.name}")
                content = test_file.read_text(encoding='utf-8')
                print(f"Content: {content}")
                test1_passed = True
            else:
                print(f"\n[FAIL] File not created: {test_file}")
                test1_passed = False

            # Test 2: Modify an existing file (hello.py)
            print("\n" + "="*80)
            print("TEST 2: Modifying existing hello.py")
            print("-" * 80)

            message2 = {
                "type": "input",
                "payload": {
                    "text": "Modify hello.py to add a comment at the top: # Modified by Aider"
                }
            }

            await ws.send(json.dumps(message2))
            print("[SENT] Modification request sent\n")

            responses_2 = []
            for i in range(50):
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    data = json.loads(response)
                    responses_2.append(data)

                    if data.get('type') == 'event':
                        payload = data.get('payload', {})
                        action = payload.get('action', '')

                        if action == 'chat_response':
                            content = payload.get('data', {}).get('content', '')
                            print(f"[RECEIVED] Chat response ({len(content)} chars)")
                            if 'Applied edit' in content or 'Modified' in content:
                                print("[OK] File was modified")

                    if data.get('type') == 'done':
                        print("[OK] Done signal received")
                        break

                except TimeoutError:
                    break

            # Wait for file operations
            await asyncio.sleep(2)

            # Check if file was modified
            hello_file = Path("data/workspaces/my_first_project_b9bffa2c/hello.py")
            if hello_file.exists():
                content = hello_file.read_text(encoding='utf-8')
                if '# Modified by Aider' in content or 'Modified by Aider' in content:
                    print("\n[SUCCESS] hello.py was modified")
                    print(f"First line: {content.split(chr(10))[0]}")
                    test2_passed = True
                else:
                    print("\n[UNCERTAIN] hello.py content:")
                    print(content[:200])
                    test2_passed = False
            else:
                print("\n[FAIL] hello.py not found")
                test2_passed = False

            # Summary
            print("\n" + "="*80)
            print("TEST SUMMARY")
            print("="*80)
            print(f"Test 1 (Create file): {'PASSED' if test1_passed else 'FAILED'}")
            print(f"Test 2 (Modify file): {'PASSED' if test2_passed else 'FAILED'}")

            if test1_passed and test2_passed:
                print("\n[SUCCESS] All tests passed! Aider integration is working!")
                return True
            else:
                print("\n[PARTIAL] Some tests failed")
                return False

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_aider_integration())
    print("\n" + "="*80)
    if result:
        print("FINAL RESULT: Aider integration is WORKING!")
    else:
        print("FINAL RESULT: Aider integration needs more work")
    print("="*80)
