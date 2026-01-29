"""Test script for advanced context strategies."""

import asyncio

from agent_os.context.advanced_strategies import SummarizerContext, KeyInfoExtractor
from agent_os.llm.litellm_impl import LiteLLMProvider
from agent_os.core.config import load_config


async def test_summarizer():
    """Test SummarizerContext strategy."""
    print("=== Testing SummarizerContext ===")

    # Create LLM provider
    config = load_config("config.yaml")
    api_key = config.llm.get_api_key()
    api_base = config.llm.get_api_base()

    llm_config = dict(config.llm.config)
    if api_key:
        llm_config["api_key"] = api_key
    if api_base:
        llm_config["api_base"] = api_base

    llm = LiteLLMProvider(**llm_config)

    # Create summarizer
    summarizer = SummarizerContext(
        llm_provider=llm,
        max_tokens=8000,
        summary_threshold=0.7,
        keep_recent=5,
    )

    # Create test messages (simulate long conversation)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "I need help with Python programming."},
        {"role": "assistant", "content": "I'd be happy to help with Python! What do you need?"},
        {"role": "user", "content": "How do I read a file in Python?"},
        {"role": "assistant", "content": "You can use the open() function: with open('file.txt', 'r') as f: content = f.read()"},
        {"role": "user", "content": "What about writing to a file?"},
        {"role": "assistant", "content": "Use open() with 'w' mode: with open('file.txt', 'w') as f: f.write('content')"},
        {"role": "user", "content": "How do I handle errors?"},
        {"role": "assistant", "content": "Use try-except blocks: try: ... except Exception as e: print(e)"},
    ]

    # Process messages
    processed, report = await summarizer.process(messages, max_tokens=8000)

    print(f"[OK] Original messages: {len(messages)}")
    print(f"[OK] Processed messages: {len(processed)}")
    print(f"[OK] Original tokens: {report.original_tokens}")
    print(f"[OK] Remaining tokens: {report.remaining_tokens}")
    print(f"[OK] Pruned count: {report.pruned_count}")
    print(f"[OK] Strategy used: {report.strategy_used}")

    if report.summary_content:
        print(f"\n[OK] Summary generated:")
        print(f"  {report.summary_content[:200]}...")

    print()


async def test_key_info_extractor():
    """Test KeyInfoExtractor strategy."""
    print("=== Testing KeyInfoExtractor ===")

    # Create LLM provider
    config = load_config("config.yaml")
    api_key = config.llm.get_api_key()
    api_base = config.llm.get_api_base()

    llm_config = dict(config.llm.config)
    if api_key:
        llm_config["api_key"] = api_key
    if api_base:
        llm_config["api_base"] = api_base

    llm = LiteLLMProvider(**llm_config)

    # Create extractor
    extractor = KeyInfoExtractor(
        llm_provider=llm,
        max_tokens=8000,
        key_info_tokens=1000,
    )

    # Create test messages
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "I want to build a REST API with FastAPI"},
        {"role": "assistant", "content": "Great choice! FastAPI is modern and fast. You'll need to install it first: pip install fastapi uvicorn"},
        {"role": "user", "content": "What are the main components?"},
        {"role": "assistant", "content": "The main components are: 1) FastAPI app instance, 2) Route decorators (@app.get, @app.post), 3) Pydantic models for request/response"},
        {"role": "user", "content": "How do I run it?"},
        {"role": "assistant", "content": "Use uvicorn: uvicorn main:app --reload. This starts a development server with auto-reload"},
    ]

    # Process messages
    processed, report = await extractor.process(messages, max_tokens=8000)

    print(f"[OK] Original messages: {len(messages)}")
    print(f"[OK] Processed messages: {len(processed)}")
    print(f"[OK] Original tokens: {report.original_tokens}")
    print(f"[OK] Remaining tokens: {report.remaining_tokens}")
    print(f"[OK] Pruned count: {report.pruned_count}")
    print(f"[OK] Strategy used: {report.strategy_used}")

    # Check if key info message was added
    key_info_msg = [m for m in processed if "[Key Information]" in m.get("content", "")]
    if key_info_msg:
        print(f"\n[OK] Key information extracted:")
        content = key_info_msg[0]["content"]
        for line in content.split("\n")[:5]:  # Show first 5 lines
            print(f"  {line}")

    print()


async def main():
    """Run all tests."""
    try:
        await test_summarizer()
        await test_key_info_extractor()
        print("=== All context strategy tests completed ===")
    except Exception as e:
        print(f"[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
