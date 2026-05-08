"""Test AI agent capabilities via WebSocket."""

import asyncio
import json
import sys
from datetime import datetime

import websockets

SESSION_ID = "f99eedc7-7016-404f-9166-08d0087f162f"
WS_URL = f"ws://127.0.0.1:8000/ws/chat/{SESSION_ID}"

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_section(title):
    print(f"\n{'='*80}")
    print(f"{Colors.HEADER}{title}{Colors.ENDC}")
    print(f"{'='*80}\n")

def print_success(text):
    print(f"{Colors.OKGREEN}[OK]{Colors.ENDC} {text}")

def print_error(text):
    print(f"{Colors.FAIL}[FAIL]{Colors.ENDC} {text}")

def print_info(text):
    print(f"{Colors.OKCYAN}[INFO]{Colors.ENDC} {text}")

def print_warning(text):
    print(f"{Colors.WARNING}[WARN]{Colors.ENDC} {text}")

async def test_websocket_connection():
    """Test 1: WebSocket connection"""
    print_section("TEST 1: WebSocket Connection")

    try:
        async with websockets.connect(WS_URL) as ws:
            print_success("WebSocket connected successfully")
            return True
    except Exception as e:
        print_error(f"WebSocket connection failed: {e}")
        return False

async def send_message_and_wait(ws, message, timeout=30):
    """Send a message and collect all responses"""
    print_info(f"Sending: {message[:60]}...")

    # Send the message
    await ws.send(json.dumps({
        "type": "input",
        "payload": {"text": message}
    }))

    # Collect responses
    responses = []
    tool_calls = []
    agent_responses = []

    start_time = asyncio.get_event_loop().time()
    timeout_time = start_time + timeout

    while asyncio.get_event_loop().time() < timeout_time:
        try:
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            data = json.loads(response)
            responses.append(data)

            payload = data.get("payload", {})
            action = payload.get("action", "")
            status = payload.get("status", "")

            if action == "tool_start":
                tool_name = payload.get("data", {}).get("tool", "unknown")
                tool_calls.append(tool_name)
                print_info(f"  Tool started: {tool_name}")

            elif action == "tool_end":
                tool_name = payload.get("data", {}).get("tool", "unknown")
                result = payload.get("data", {}).get("result", "")[:60]
                print_success(f"  Tool completed: {tool_name} -> {result}...")

            elif action == "chat_response":
                content = payload.get("data", {}).get("content", "")
                agent_responses.append(content)
                print_success(f"  Agent response: {content[:80]}...")

                # If we have a response and no tools are being called, break
                if not tool_calls and "tool" not in str(data).lower():
                    # Wait a bit more to ensure no tool calls coming
                    await asyncio.sleep(1)
                    break

        except TimeoutError:
            continue
        except Exception as e:
            print_error(f"Error receiving: {e}")
            break

    return {
        "responses": responses,
        "tool_calls": tool_calls,
        "agent_responses": agent_responses
    }

async def test_file_modification():
    """Test 2: AI reads and modifies existing file"""
    print_section("TEST 2: AI File Modification")

    try:
        async with websockets.connect(WS_URL) as ws:
            # Wait for connection
            await asyncio.sleep(1)

            # Send modification request
            message = "修改guess_number.py，增加猜测次数限制功能，玩家只能猜7次，如果用完次数则提示游戏失败并显示正确答案"
            result = await send_message_and_wait(ws, message, timeout=60)

            print(f"\n{Colors.BOLD}Results:{Colors.ENDC}")
            print(f"  Total responses: {len(result['responses'])}")
            print(f"  Tool calls made: {len(result['tool_calls'])}")
            print(f"  Tools used: {result['tool_calls']}")
            print(f"  Agent responses: {len(result['agent_responses'])}")

            # Verify expected tools were called
            expected_tools = ['read_file', 'write_file']
            tools_used = result['tool_calls']

            success = True
            for tool in expected_tools:
                if tool in tools_used:
                    print_success(f"  {tool} was called")
                else:
                    print_error(f"  {tool} was NOT called")
                    success = False

            if success:
                print_success("\n✓ Test PASSED: AI successfully read and modified file")
                return True
            else:
                print_error("\n✗ Test FAILED: AI did not use required tools")
                return False

    except Exception as e:
        print_error(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_multiturn_conversation():
    """Test 3: Multi-turn conversation with memory"""
    print_section("TEST 3: Multi-turn Conversation & Memory")

    try:
        async with websockets.connect(WS_URL) as ws:
            await asyncio.sleep(1)

            # Turn 1: Ask AI to create a simple file
            print_info("Turn 1: Creating a file...")
            result1 = await send_message_and_wait(ws, "创建一个名为hello.txt的文件，内容是'Hello from AI'", timeout=30)

            # Turn 2: Ask AI to modify the same file
            print_info("\nTurn 2: Modifying the file...")
            result2 = await send_message_and_wait(ws, "修改hello.txt，在内容后面加上' - Modified'", timeout=30)

            # Turn 3: Ask AI what files exist
            print_info("\nTurn 3: Listing files...")
            result3 = await send_message_and_wait(ws, "列出当前目录的文件", timeout=30)

            print(f"\n{Colors.BOLD}Results:{Colors.ENDC}")
            print(f"  Turn 1 tools: {result1['tool_calls']}")
            print(f"  Turn 2 tools: {result2['tool_calls']}")
            print(f"  Turn 3 tools: {result3['tool_calls']}")

            # Check if AI shows continuity
            if 'write_file' in result1['tool_calls'] and 'write_file' in result2['tool_calls']:
                print_success("\n✓ Test PASSED: AI maintained context across multiple turns")
                return True
            else:
                print_error("\n✗ Test FAILED: AI did not maintain context properly")
                return False

    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def verify_file_modification():
    """Verify the actual file was modified"""
    print_section("TEST 4: Verify File Content")

    try:
        with open("D:/Codes/whyme/data/workspaces/test-python-app/guess_number.py", encoding="utf-8") as f:
            content = f.read()

        # Check if the modification is present
        if "max_attempts" in content or "7" in content or "次" in content:
            print_success("File was modified with attempt limit feature")

            # Show relevant lines
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if any(keyword in line for keyword in ["max_attempts", "attempt", "次", "7"]):
                    print(f"  Line {i}: {line}")

            return True
        else:
            print_error("File was NOT modified (no attempt limit found)")
            print_warning("Current file still has original content")
            return False

    except Exception as e:
        print_error(f"Failed to read file: {e}")
        return False

async def main():
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*80}")
    print("AI AGENT CAPABILITY TEST SUITE")
    print(f"{'='*80}{Colors.ENDC}")
    print(f"\nSession ID: {SESSION_ID}")
    print(f"WebSocket URL: {WS_URL}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # Test 1: Connection
    results['connection'] = await test_websocket_connection()

    if not results['connection']:
        print_error("Cannot proceed - WebSocket connection failed")
        return

    await asyncio.sleep(2)

    # Test 2: File modification
    results['file_modification'] = await test_file_modification()
    await asyncio.sleep(2)

    # Test 3: Multi-turn conversation
    results['multiturn'] = await test_multiturn_conversation()
    await asyncio.sleep(2)

    # Test 4: Verify actual file
    results['file_content'] = await verify_file_modification()

    # Summary
    print_section("TEST SUMMARY")
    print(f"\n1. WebSocket Connection:      {Colors.OKGREEN}PASS{Colors.ENDC if results['connection'] else Colors.FAIL}FAIL{Colors.ENDC}")
    print(f"2. AI File Modification:      {Colors.OKGREEN}PASS{Colors.ENDC if results['file_modification'] else Colors.FAIL}FAIL{Colors.ENDC}")
    print(f"3. Multi-turn Conversation:   {Colors.OKGREEN}PASS{Colors.ENDC if results['multiturn'] else Colors.FAIL}FAIL{Colors.ENDC}")
    print(f"4. File Content Verification: {Colors.OKGREEN}PASS{Colors.ENDC if results['file_content'] else Colors.FAIL}FAIL{Colors.ENDC}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    print(f"\n{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.ENDC}")

    if passed == total:
        print_success("\n✓ All tests passed!")
        return 0
    else:
        print_error(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    # Fix Windows event loop
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    exit_code = asyncio.run(main())
    sys.exit(exit_code)
