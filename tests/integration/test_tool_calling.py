"""Test script to diagnose tool calling with LiteLLM and DeepSeek."""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_tool_calling():
    """Test if the LLM properly calls tools."""
    from agent_os.llm.litellm_impl import LiteLLMProvider

    # Initialize provider with current config
    api_key = os.getenv("API_KEY")
    api_base = os.getenv("BASE_URL")

    print(f"API Key: {api_key[:20]}... if exists")
    print(f"API Base: {api_base}")

    provider = LiteLLMProvider(
        model="openai/DeepSeek-V3.1",
        api_base=api_base,
        api_key=api_key,
    )

    # Test messages
    messages = [
        {"role": "system", "content": "You are a coding assistant. When asked to modify files or run commands, you MUST use the available tools."},
        {"role": "user", "content": "Create a file called test.txt with content 'Hello World'"}
    ]

    # Define tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file. Overwrites existing content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The file path relative to workspace root"},
                        "content": {"type": "string", "description": "The full content to write to the file"}
                    },
                    "required": ["path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Run a shell command in the sandbox.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The shell command to execute"}
                    },
                    "required": ["command"]
                }
            }
        }
    ]

    print("\n" + "="*80)
    print("TESTING TOOL CALLING WITH DeepSeek-V3.1")
    print("="*80)
    print(f"\nModel: openai/DeepSeek-V3.1")
    print(f"API Base: {api_base}")
    print(f"\nSending {len(messages)} messages with {len(tools)} tools...")
    print(f"\nMessage: {messages[-1]['content']}")

    try:
        response = await provider.complete(
            messages=messages,
            tools=tools
        )

        print(f"\n" + "="*80)
        print("RESPONSE RECEIVED")
        print("="*80)
        print(f"Response keys: {list(response.keys())}")
        print(f"Content: {response.get('content', '')[:500]}")
        print(f"\nTool calls present: {'tool_calls' in response}")

        if 'tool_calls' in response and response['tool_calls']:
            print(f"\n[OK] SUCCESS! Tool calls detected:")
            for tc in response['tool_calls']:
                print(f"  - {tc['function']['name']}: {tc['function']['arguments'][:100]}...")
        else:
            print(f"\n[FAIL] FAILURE! No tool calls in response.")
            print(f"\nThe LLM responded with text instead of calling tools.")
            print(f"This suggests either:")
            print(f"  1. The model doesn't support function calling")
            print(f"  2. The tool format is incompatible with the model")
            print(f"  3. The system prompt needs to be more explicit")
            print(f"  4. The API endpoint doesn't support function calling")

    except Exception as e:
        print(f"\n[ERROR] ERROR: {e}")
        import traceback
        traceback.print_exc()

async def test_without_tools():
    """Test basic completion without tools."""
    from agent_os.llm.litellm_impl import LiteLLMProvider

    api_key = os.getenv("API_KEY")
    api_base = os.getenv("BASE_URL")

    provider = LiteLLMProvider(
        model="openai/DeepSeek-V3.1",
        api_base=api_base,
        api_key=api_key,
    )

    messages = [
        {"role": "user", "content": "Say 'Hello, this is a test'"}
    ]

    print("\n" + "="*80)
    print("TESTING BASIC COMPLETION (NO TOOLS)")
    print("="*80)

    try:
        response = await provider.complete(messages=messages)
        print(f"[OK] SUCCESS! Response: {response.get('content', '')[:200]}")
    except Exception as e:
        print(f"[ERROR] ERROR: {e}")

async def test_with_gpt4o():
    """Test with GPT-4o-mini to compare behavior."""
    from agent_os.llm.litellm_impl import LiteLLMProvider

    # Note: This requires OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[WARN] Skipping GPT-4o-mini test (no OPENAI_API_KEY)")
        return

    provider = LiteLLMProvider(
        model="openai/gpt-4o-mini",
    )

    messages = [
        {"role": "system", "content": "You are a coding assistant. When asked to modify files or run commands, you MUST use the available tools."},
        {"role": "user", "content": "Create a file called test.txt with content 'Hello World'"}
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a file. Overwrites existing content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "The file path"},
                        "content": {"type": "string", "description": "The content to write"}
                    },
                    "required": ["path", "content"]
                }
            }
        }
    ]

    print("\n" + "="*80)
    print("TESTING WITH GPT-4O-MINI (FOR COMPARISON)")
    print("="*80)

    try:
        response = await provider.complete(messages=messages, tools=tools)
        print(f"Response keys: {list(response.keys())}")
        print(f"Content: {response.get('content', '')[:200]}")
        print(f"Tool calls present: {'tool_calls' in response}")

        if 'tool_calls' in response:
            print(f"[OK] GPT-4o-mini successfully called tools!")
    except Exception as e:
        print(f"[ERROR] ERROR: {e}")

if __name__ == "__main__":
    # Fix Windows subprocess issue
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    print("="*80)
    print("TOOL CALLING DIAGNOSTIC TEST")
    print("="*80)

    # Run tests
    asyncio.run(test_without_tools())
    asyncio.run(test_tool_calling())
    asyncio.run(test_with_gpt4o())

    print("\n" + "="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)
