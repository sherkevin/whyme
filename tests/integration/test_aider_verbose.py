"""Verbose test of AiderAgent."""

import asyncio
import sys
sys.path.insert(0, "src")

from agent_os.agent_aider import AiderAgent
from pathlib import Path

async def test_verbose():
    """Test AiderAgent with verbose output."""
    workspace = Path("data/workspaces/verbose_test")
    workspace.mkdir(parents=True, exist_ok=True)

    agent = AiderAgent(
        session_id="verbose_test",
        workspace_root=str(workspace)
    )

    message = "Create a file called hello_verbose.py with print('Hello from Aider!')"

    print("="*80)
    print("Sending message to aider...")
    print("="*80)

    result = await agent.chat(message)

    # Write full result to file
    with open("aider_verbose_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Content:\n{result.get('content', 'No content')}\n\n")
        f.write(f"File changes: {result.get('file_changes', [])}\n")

    print("Full output written to aider_verbose_output.txt")

    # Check file
    hello_file = workspace / "hello_verbose.py"
    if hello_file.exists():
        print(f"\n[SUCCESS] File created!")
        print(hello_file.read_text(encoding='utf-8'))
    else:
        print(f"\n[FAIL] File not created")
        print(f"Workspace contents: {list(workspace.iterdir())}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(test_verbose())
