"""Test creating and modifying Python code with aider."""

import asyncio
import sys
sys.path.insert(0, "src")

from agent_os.agent_aider import AiderAgent
from pathlib import Path

async def test_python_workflow():
    """Test creating and modifying Python code."""
    workspace = Path("data/workspaces/python_test")
    workspace.mkdir(parents=True, exist_ok=True)

    agent = AiderAgent(
        session_id="python_test",
        workspace_root=str(workspace)
    )

    print("="*80)
    print("STEP 1: Create a Python calculator file")
    print("="*80)

    message1 = "Create a file calculator.py with a simple calculator that can add, subtract, multiply, and divide two numbers."
    result1 = await agent.chat(message1)

    print(f"Response: {result1.get('content', '')[:200]}")

    # Check file
    calc_file = workspace / "calculator.py"
    if calc_file.exists():
        print(f"\n[SUCCESS] calculator.py created!")
        print(f"Content:\n{calc_file.read_text(encoding='utf-8')}")
    else:
        print(f"\n[FAIL] calculator.py not created")
        return

    print("\n" + "="*80)
    print("STEP 2: Add a power function to the calculator")
    print("="*80)

    message2 = "Add a power(x, y) function to calculator.py that calculates x raised to the power of y."
    result2 = await agent.chat(message2)

    print(f"Response: {result2.get('content', '')[:200]}")

    # Check file was modified
    if calc_file.exists():
        content = calc_file.read_text(encoding='utf-8')
        print(f"\nUpdated content:\n{content}")

        if 'power' in content.lower() or 'def power' in content:
            print(f"\n[SUCCESS] Power function added!")
        else:
            print(f"\n[UNCERTAIN] Power function not found")
    else:
        print(f"\n[FAIL] calculator.py disappeared")

    print("\n" + "="*80)
    print("STEP 3: Test the calculator by adding a main block")
    print("="*80)

    message3 = 'Add a main block to calculator.py that tests the functions: print(calculator.add(5, 3)) and print(calculator.power(2, 3))'
    result3 = await agent.chat(message3)

    print(f"Response: {result3.get('content', '')[:200]}")

    # Check final content
    if calc_file.exists():
        content = calc_file.read_text(encoding='utf-8')
        print(f"\nFinal content:\n{content}")

        if '__main__' in content or 'if __name__' in content:
            print(f"\n[SUCCESS] Main block added!")
        else:
            print(f"\n[UNCERTAIN] Main block not found")

    print("\n" + "="*80)
    print("WORKFLOW COMPLETE")
    print("="*80)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(test_python_workflow())
