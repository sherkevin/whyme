"""Simple test to verify aider initialization."""

import asyncio
import sys

sys.path.insert(0, "src")

async def test_aider_init():
    """Test if aider Coder can be initialized."""
    print("="*80)
    print("TEST: Aider Coder Initialization")
    print("="*80)

    try:
        from pathlib import Path

        from agent_os.capabilities.coding.aider_integration import AiderCoderIntegration

        workspace = Path("data/workspaces/test_init")
        workspace.mkdir(parents=True, exist_ok=True)

        print("\n1. Creating AiderCoderIntegration...")
        integration = AiderCoderIntegration(
            workspace_root=str(workspace),
            model_name="openai/DeepSeek-V3.1"
        )

        print("2. Initializing...")
        await integration.initialize()

        print("3. Checking if coder exists...")
        if integration.coder:
            print("   ✓ Coder created successfully!")
            print(f"   Type: {type(integration.coder)}")
            print(f"   Model: {integration.coder.main_model.name}")
            return True
        else:
            print("   ✗ Coder is None")
            return False

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    result = asyncio.run(test_aider_init())
    print(f"\n{'='*80}")
    print(f"Test {'PASSED' if result else 'FAILED'}")
    print(f"{'='*80}")
