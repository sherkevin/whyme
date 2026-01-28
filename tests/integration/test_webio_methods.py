"""Test that WebIO has all required methods."""

import asyncio
import sys
sys.path.insert(0, "src")

from agent_os.capabilities.coding.aider_integration import AiderCoderIntegration

async def test_webio_methods():
    """Test that WebIO has all required methods."""
    print("="*80)
    print("TEST: WebIO Methods Check")
    print("="*80)

    # Create a dummy instance just to get the WebIO class
    from pathlib import Path

    workspace = Path("data/workspaces/test_methods")
    workspace.mkdir(parents=True, exist_ok=True)

    integration = AiderCoderIntegration(
        workspace_root=str(workspace),
        model_name="openai/DeepSeek-V3.1"
    )

    # Initialize to create the WebIO instance
    await integration.initialize()

    # Check for all required methods
    webio = integration.io

    required_methods = [
        'tool_output',
        'tool_error',
        'tool_warning',
        'get_input',
        'user_input',
        'confirm_ask',
        'offer_url',
        'llm_started',  # This was causing the error
        'llm_response',
        'get_file_content',
        'rule',
        'autocomplete',
        'log_llm_history',
        'get_llm_history_messages',
        'write_chat_history',
        'read_image',
        'is_dumb_terminal'
    ]

    required_attributes = [
        'pretty',
        'encoding',
        'placeholder'
    ]

    print("\nChecking methods:")
    all_good = True
    for method in required_methods:
        has_method = hasattr(webio, method)
        status = "[OK]" if has_method else "[FAIL]"
        print(f"  {status} {method}: {has_method}")
        if not has_method:
            all_good = False

    print("\nChecking attributes:")
    for attr in required_attributes:
        has_attr = hasattr(webio, attr)
        status = "[OK]" if has_attr else "[FAIL]"
        print(f"  {status} {attr}: {has_attr}")
        if not has_attr:
            all_good = False

    # Test that llm_started can actually be called
    print("\nTesting llm_started() call:")
    try:
        webio.llm_started()
        print("  [OK] llm_started() called successfully")
    except Exception as e:
        print(f"  [FAIL] llm_started() failed: {e}")
        all_good = False

    print("\n" + "="*80)
    if all_good:
        print("All checks PASSED")
    else:
        print("Some checks FAILED")
    print("="*80)

    return all_good

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    result = asyncio.run(test_webio_methods())
    sys.exit(0 if result else 1)
