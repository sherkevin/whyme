"""Test to check what's in the output buffer."""

import asyncio
import sys

sys.path.insert(0, "src")

from pathlib import Path

from agent_os.agent_aider import AiderAgent


async def test_output():
    """Test what's in output buffer."""
    workspace = Path("data/workspaces/output_test")
    workspace.mkdir(parents=True, exist_ok=True)

    agent = AiderAgent(
        session_id="output_test",
        workspace_root=str(workspace)
    )

    message = "Create a file hello.txt with content: Hello World"

    result = await agent.chat(message)

    # Get the aider integration
    aider = await agent._get_aider()

    print("\nOutput buffer contents:")
    for i, (msg_type, msg) in enumerate(aider.io.output_buffer):
        print(f"{i+1}. [{msg_type}] {msg[:100] if len(msg) > 100 else msg}")

    print("\nCoder attributes:")
    print(f"  abs_fnames: {aider.coder.abs_fnames if aider.coder else 'No coder'}")
    if hasattr(aider.coder, 'partial_response_content'):
        print(f"  partial_response_content: {aider.coder.partial_response_content[:200] if aider.coder.partial_response_content else 'None'}")

    print("\nWorkspace files:")
    for f in workspace.rglob("*"):
        if f.is_file():
            print(f"  {f.name}: {f.stat().st_size} bytes")
            if f.stat().st_size > 0 and f.stat().st_size < 1000:
                print(f"    Content: {f.read_text(encoding='utf-8')}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(test_output())
