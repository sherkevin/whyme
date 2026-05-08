"""Direct test of aider"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

os.environ["AGENTOS_SANDBOX"] = "local"

from pathlib import Path

from agent_os.capabilities.coding.aider_integration import AiderCoderIntegration


async def test():
    workspace = Path("./data/workspaces/my_first_project_b9bffa2c")
    print(f"Workspace: {workspace.absolute()}")
    print(f"Workspace exists: {workspace.exists()}")

    aider = AiderCoderIntegration(
        session_id="test",
        workspace_root=str(workspace)
    )

    try:
        await aider.initialize()
        print("Aider initialized")
    except Exception as e:
        print(f"Initialize failed: {e}")
        import traceback
        traceback.print_exc()
        return

    result = await aider.run_message(None, "创建一个文件test.txt，内容：Hello")
    print(f"Result: {result}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test())
