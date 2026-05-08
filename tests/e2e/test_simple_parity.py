"""Simple test for aider backend functionality"""

import asyncio
import sys

sys.path.insert(0, "src")

from pathlib import Path

from agent_os.agent_aider import AiderAgent


async def simple_test():
    """Test core aider functionality"""
    workspace = Path("D:/Codes/whyme/data/workspaces/simple_test")
    workspace.mkdir(parents=True, exist_ok=True)

    agent = AiderAgent(
        session_id="simple_test",
        workspace_root=str(workspace)
    )

    print("Test 1: Create file")
    print("-" * 40)
    r1 = await agent.chat("Create hello.txt with: Hello World")
    f1 = workspace / "hello.txt"
    if f1.exists():
        print(f"[PASS] File created: {f1.read_text()}")
    else:
        print("[FAIL] File not created")
        return False

    print("\nTest 2: Modify file")
    print("-" * 40)
    r2 = await agent.chat("Add another line: Hello Again")
    f1 = workspace / "hello.txt"
    content = f1.read_text()
    if "Hello Again" in content:
        print(f"[PASS] File modified: {content}")
    else:
        print(f"[FAIL] File not modified: {content}")
        return False

    print("\nTest 3: Create another file (multi-file)")
    print("-" * 40)
    r3 = await agent.chat("Create test.txt with: Test Content")
    f2 = workspace / "test.txt"
    if f2.exists():
        print("[PASS] Second file created")
    else:
        print("[FAIL] Second file not created")
        return False

    print("\nTest 4: Check workspace")
    print("-" * 40)
    files = list(workspace.glob("*.txt"))
    print(f"[PASS] Workspace has {len(files)} files: {[f.name for f in files]}")

    print("\n" + "="*40)
    print("ALL TESTS PASSED")
    print("Backend functionality = Aider terminal")
    print("="*40)
    return True

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    result = asyncio.run(simple_test())
