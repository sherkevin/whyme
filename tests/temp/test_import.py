"""Test if the imported WebIO is correct."""

import sys

sys.path.insert(0, "src")

# Import the module
# Initialize it (this will create WebIO)
import asyncio
from pathlib import Path

from agent_os.capabilities.coding.aider_integration import AiderCoderIntegration


async def test():
    workspace = Path("data/workspaces/import_test")
    workspace.mkdir(parents=True, exist_ok=True)

    integration = AiderCoderIntegration(
        workspace_root=str(workspace),
        model_name="openai/DeepSeek-V3.1"
    )

    # Initialize to create WebIO
    await integration.initialize()

    # Check WebIO
    webio = integration.io

    print("WebIO attributes:")
    for attr in dir(webio):
        if not attr.startswith('_'):
            val = getattr(webio, attr)
            if not callable(val):
                print(f"  {attr} = {type(val).__name__}")

    # Check if tool_output is callable
    print(f"\ntool_output is callable: {callable(webio.tool_output)}")
    print(f"tool_output type: {type(webio.tool_output)}")

    # Check if there's a tool_output attribute that's a list
    if hasattr(webio, 'tool_output') and isinstance(getattr(webio, 'tool_output'), list):
        print("ERROR: tool_output is a list!")

asyncio.run(test())
