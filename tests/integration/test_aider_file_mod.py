"""Test aider file modification through WebSocket."""

import asyncio
import json
import time

import websockets


async def test_aider_file_mod():
    """Test that aider can create and modify files."""
    session_id = "b9bffa2c-edd6-40a2-bffe-f203b7ba5dae"

    print("="*80)
    print("TEST: Aider File Modification")
    print("="*80)

    # Connect to WebSocket
    uri = f"ws://127.0.0.1:8000/ws/chat/{session_id}"
    print(f"\nConnecting to {uri}...")

    try:
        async with websockets.connect(uri) as ws:
            print("Connected!")

            # Test 1: Create a new file
            print("\n" + "="*80)
            print("Test 1: Create a new file")
            print("="*80)

            message1 = {
                "type": "input",
                "payload": {
                    "text": "Create a file called test_calc.py with a simple calculator that can add, subtract, multiply, and divide two numbers."
                }
            }

            print(f"Sending: {message1['payload']['text'][:60]}...")
            await ws.send(json.dumps(message1))

            # Collect responses
            responses = []
            start_time = time.time()
            timeout = 60  # 60 seconds timeout

            while time.time() - start_time < timeout:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(response)
                    responses.append(data)
                    print(f"Received: {data['type']}")

                    # Print full data structure
                    print(f"  Full data: {json.dumps(data, ensure_ascii=False)[:200]}...")

                    # Print content and payload if available
                    if 'payload' in data:
                        payload = data['payload']
                        if isinstance(payload, dict):
                            if 'content' in payload:
                                content = payload['content']
                                print(f"  Content preview: {content[:100]}...")
                            if 'file_changes' in payload:
                                print(f"  File changes: {payload['file_changes']}")

                    # Check if done
                    if data.get('type') == 'done':
                        break
                except TimeoutError:
                    # Check if we've received enough responses
                    if len(responses) > 2:
                        break
                    continue

            print(f"Received {len(responses)} responses")

            # Wait a bit for file to be written
            await asyncio.sleep(3)

            # Check if file was created
            from pathlib import Path
            test_file = Path("data/workspaces/my_first_project_b9bffa2c/test_calc.py")
            if test_file.exists():
                print(f"\n[SUCCESS] File created: {test_file}")
                print(f"File size: {test_file.stat().st_size} bytes")
            else:
                print(f"\n[FAIL] File not created: {test_file}")

            # Test 2: Modify the file
            print("\n" + "="*80)
            print("Test 2: Modify the file")
            print("="*80)

            message2 = {
                "type": "input",
                "payload": {
                    "text": "Add a power function to test_calc.py that calculates x^y."
                }
            }

            print(f"Sending: {message2['payload']['text'][:60]}...")
            await ws.send(json.dumps(message2))

            # Collect responses
            responses = []
            start_time = time.time()

            while time.time() - start_time < timeout:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    data = json.loads(response)
                    responses.append(data)
                    print(f"Received: {data['type']}")

                    # Check if done
                    if data.get('type') == 'done':
                        break
                except TimeoutError:
                    if len(responses) > 2:
                        break
                    continue

            print(f"Received {len(responses)} responses")

            # Wait a bit for file to be modified
            await asyncio.sleep(3)

            # Check if file was modified (should be larger)
            if test_file.exists():
                new_size = test_file.stat().st_size
                print(f"\nFile size after modification: {new_size} bytes")

                # Read and display file content
                content = test_file.read_text(encoding='utf-8')
                print(f"\nFile content:\n{'-'*60}")
                print(content[:500])  # First 500 chars
                if len(content) > 500:
                    print(f"\n... ({len(content) - 500} more chars)")
                print('-'*60)

                # Check if power function was added
                if 'power' in content.lower() or 'pow' in content.lower() or '**' in content:
                    print("\n[SUCCESS] Power function appears to be added!")
                else:
                    print("\n[UNCERTAIN] Cannot confirm if power function was added")
            else:
                print(f"\n[FAIL] File disappeared: {test_file}")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("Test completed")
    print("="*80)

if __name__ == "__main__":
    if __name__ == "__main__":
        asyncio.run(test_aider_file_mod())
