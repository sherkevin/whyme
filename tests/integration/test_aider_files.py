"""Test to check what files aider is tracking."""

import asyncio
import sys

sys.path.insert(0, "src")

from pathlib import Path

from agent_os.agent_aider import AiderAgent


async def test_files():
    """Test what files aider creates."""
    workspace = Path("data/workspaces/files_test")
    workspace.mkdir(parents=True, exist_ok=True)

    agent = AiderAgent(
        session_id="files_test",
        workspace_root=str(workspace)
    )

    message = "Create a file hello.py with: print('Hello World')"

    print("Sending message...")
    result = await agent.chat(message)

    print(f"\nResult content: {result.get('content', '')[:200]}")
    print(f"File changes: {result.get('file_changes', [])}")

    # Get the aider integration directly
    aider = await agent._get_aider()

    # Check what files aider knows about
    print(f"\nCoder abs_fnames: {aider.coder.abs_fnames if aider.coder else 'No coder'}")

    # Check workspace contents
    print("\nWorkspace contents:")
    for item in workspace.iterdir():
        print(f"  - {item.name}")

    # List all files in workspace
    all_files = list(workspace.rglob("*"))
    print(f"\nAll files (recursive): {[str(f.relative_to(workspace)) for f in all_files if f.is_file()]}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(test_files())
