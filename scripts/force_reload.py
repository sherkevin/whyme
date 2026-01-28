"""Force reload by touching the module file."""

import time
import sys
sys.path.insert(0, "src")

# Touch the file to trigger reload
from pathlib import Path

aider_file = Path("src/agent_os/capabilities/coding/aider_integration.py")
aider_file.touch()

print("Touched aider_integration.py to force reload")
print("Wait 5 seconds for server to reload...")
time.sleep(5)

# Now test if it's working
import asyncio
from agent_os.capabilities.coding.aider_integration import AiderCoderIntegration

async def test():
    workspace = Path("data/workspaces/force_reload_test")
    workspace.mkdir(parents=True, exist_ok=True)

    integration = AiderCoderIntegration(
        workspace_root=str(workspace),
        model_name="openai/DeepSeek-V3.1"
    )

    await integration.initialize()

    # Check
    webio = integration.io
    print(f"tool_output is callable: {callable(webio.tool_output)}")

    # Try to run a message
    result = await integration.run_message(None, "Create a file test.txt with: Hello")
    print(f"Result length: {len(result)}")
    if "Error" in result and "list" in result and "callable" in result:
        print("ERROR: Still using old code!")
        return False
    else:
        print("SUCCESS: Using new code!")

    # Check file
    test_file = workspace / "test.txt"
    if test_file.exists():
        print(f"File created: {test_file}")
        print(f"Content: {test_file.read_text(encoding='utf-8')}")
        return True
    return False

result = asyncio.run(test())
sys.exit(0 if result else 1)
