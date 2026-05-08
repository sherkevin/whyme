#!/usr/bin/env python3
"""Test script for LLM integration.

Usage:
    1. Copy .env.example to .env
    2. Fill in your API_KEY and BASE_URL in .env
    3. Run: uv run python test_llm.py
"""

import asyncio
import os

from agent_os.agent import Agent
from agent_os.llm.litellm_impl import LiteLLMProvider


async def test_direct_llm():
    """Test direct LLM provider."""
    print("=" * 50)
    print("Testing direct LLM provider...")
    print("=" * 50)

    api_key = os.getenv("API_KEY")
    api_base = os.getenv("BASE_URL")

    if not api_key:
        print("ERROR: API_KEY not found in environment")
        print("Please set API_KEY in your .env file")
        return False

    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    print(f"API Base: {api_base}")

    try:
        llm = LiteLLMProvider(
            model="openai/gpt-4o-mini",
            api_base=api_base,
            api_key=api_key,
        )

        response = await llm.complete(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello, AgentOS!' in exactly this format."},
            ],
        )

        print("\nResponse:")
        print(f"  Content: {response['content']}")
        print(f"  Model: {response.get('model', 'unknown')}")
        print(f"  Usage: {response.get('usage', {})}")

        return True
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent():
    """Test Agent with config file."""
    print("\n" + "=" * 50)
    print("Testing Agent with config.yaml...")
    print("=" * 50)

    try:
        agent = Agent.from_config_file("config.yaml")
        await agent.initialize_llm()

        response = await agent.chat(
            "Hello! Please introduce yourself in one sentence."
        )

        print("\nAgent Response:")
        print(f"  {response['content']}")
        print(f"\nConversation history length: {len(agent.conversation_history)}")

        return True
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_with_tools():
    """Test Agent with custom tools."""
    print("\n" + "=" * 50)
    print("Testing Agent with custom tools...")
    print("=" * 50)

    # Define a simple tool
    def get_weather(location: str) -> str:
        """Get the current weather for a location.

        Args:
            location: The city name

        Returns:
            Weather description
        """
        # Simulated weather data
        weather_data = {
            "Beijing": "Sunny, 25°C",
            "Shanghai": "Cloudy, 22°C",
            "New York": "Rainy, 15°C",
            "London": "Foggy, 12°C",
        }
        return weather_data.get(location, f"Weather data for {location} not available")

    try:
        agent = Agent.from_config_file("config.yaml")
        await agent.initialize_llm()

        # Register the tool
        await agent.tool_registry.register_python_tool(get_weather)

        # Get tool definitions
        tools = await agent.tool_registry.get_definitions()
        print(f"\nRegistered tools: {[t['function']['name'] for t in tools]}")

        # Chat with the agent
        response = await agent.chat("What's the weather like in Beijing?")

        print("\nAgent Response:")
        print(f"  {response['content']}")

        if "tool_calls" in response:
            print(f"\nTool calls made: {len(response['tool_calls'])}")

        return True
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    # Check for environment variables
    if not os.getenv("API_KEY"):
        print("WARNING: API_KEY not found in environment")
        print("Please create a .env file with your API credentials")
        print("See .env.example for the format")
        return

    results = []

    # Run tests
    results.append(("Direct LLM", await test_direct_llm()))
    results.append(("Agent", await test_agent()))
    results.append(("Agent with Tools", await test_agent_with_tools()))

    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    asyncio.run(main())
