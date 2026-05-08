"""Simple direct test of aider."""

import asyncio
import sys

sys.path.insert(0, "src")

import time
from pathlib import Path

from agent_os.agent_aider import AiderAgent


async def test_direct():
    """Test AiderAgent directly without WebSocket."""
    print("="*80)
    print("DIRECT AIDER TEST (no WebSocket)")
    print("="*80)

    workspace = Path("data/workspaces/direct_test_final")
    workspace.mkdir(parents=True, exist_ok=True)

    agent = AiderAgent(
        session_id="direct_test_final",
        workspace_root=str(workspace)
    )

    print("\nTest 1: Creating file...")
    print("-" * 80)

    start_time = time.time()
    result = await agent.chat("Create a file hello_direct.txt with: Hello Direct Test!")
    elapsed = time.time() - start_time

    print(f"Elapsed time: {elapsed:.2f} seconds")
    print(f"Response length: {len(result.get('content', ''))}")
    print(f"File changes: {result.get('file_changes', [])}")

    # Check file
    test_file = workspace / "hello_direct.txt"
    if test_file.exists():
        content = test_file.read_text(encoding='utf-8')
        print("\n[SUCCESS] File created!")
        print(f"Content: {content}")
        return True
    else:
        print("\n[FAIL] File not created")

        # Print error details
        if 'error' in result:
            print(f"Error: {result['error']}")

        content = result.get('content', '')
        if content:
            print(f"Response preview: {content[:500]}")

        return False

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    result = asyncio.run(test_direct())
    print("\n" + "="*80)
    if result:
        print("DIRECT TEST PASSED!")
    else:
        print("DIRECT TEST FAILED")
    print("="*80)
