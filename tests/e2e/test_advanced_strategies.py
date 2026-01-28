"""Tests for advanced context management strategies."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from agent_os.context.advanced_strategies import KeyInfoExtractor, SummarizerContext


class MockLLMProvider:
    """Mock LLM provider for testing."""

    def __init__(self, response: str = "Test summary") -> None:
        self.response = response
        self.call_count = 0

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Mock generate method."""
        self.call_count += 1
        return {"content": self.response}


class TestSummarizerContext:
    """Test suite for SummarizerContext."""

    @pytest.mark.asyncio
    async def test_no_summarization_needed(self) -> None:
        """Test that no summarization occurs when under threshold."""
        llm = MockLLMProvider()
        context = SummarizerContext(llm, max_tokens=1000, summary_threshold=0.7)

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        processed, report = await context.process(messages, max_tokens=1000)

        assert len(processed) == len(messages)
        assert report.strategy_used == "none"
        assert report.pruned_count == 0
        assert llm.call_count == 0

    @pytest.mark.asyncio
    async def test_summarization_triggered(self) -> None:
        """Test that summarization occurs when over threshold."""
        llm = MockLLMProvider(response="Summary of previous conversation")
        context = SummarizerContext(
            llm, max_tokens=100, summary_threshold=0.5, keep_recent=2
        )

        # Create many messages to trigger summarization
        messages = [
            {"role": "user", "content": "Message " + str(i) * 50}
            for i in range(10)
        ]

        processed, report = await context.process(messages, max_tokens=100)

        # Should have fewer messages after summarization
        assert len(processed) < len(messages)
        assert report.strategy_used == "summarization"
        assert report.original_tokens > report.remaining_tokens
        assert llm.call_count == 1

        # Check that summary message was added
        summary_found = any(
            "Previous conversation summary" in m.get("content", "")
            for m in processed
        )
        assert summary_found

    @pytest.mark.asyncio
    async def test_keeps_recent_messages(self) -> None:
        """Test that recent messages are preserved."""
        llm = MockLLMProvider()
        context = SummarizerContext(
            llm, max_tokens=100, summary_threshold=0.5, keep_recent=3
        )

        messages = [
            {"role": "user", "content": "Old message " + str(i) * 50}
            for i in range(5)
        ] + [
            {"role": "user", "content": f"Recent {i}"}
            for i in range(3)
        ]

        processed, report = await context.process(messages, max_tokens=100)

        # Recent messages should be in processed
        recent_contents = [m.get("content", "") for m in processed[-3:]]
        assert "Recent 0" in recent_contents[0]
        assert "Recent 1" in recent_contents[1]
        assert "Recent 2" in recent_contents[2]

    @pytest.mark.asyncio
    async def test_preserves_system_messages(self) -> None:
        """Test that system messages are preserved."""
        llm = MockLLMProvider()
        context = SummarizerContext(
            llm, max_tokens=100, summary_threshold=0.5, keep_recent=2
        )

        messages = [
            {"role": "system", "content": "You are a helpful assistant"}
        ] + [
            {"role": "user", "content": "Message " + str(i) * 50}
            for i in range(5)
        ]

        processed, report = await context.process(messages, max_tokens=100)

        # System message should be first
        assert processed[0]["role"] == "system"
        assert "helpful assistant" in processed[0]["content"]

    @pytest.mark.asyncio
    async def test_insufficient_messages(self) -> None:
        """Test handling when not enough messages to summarize."""
        llm = MockLLMProvider()
        context = SummarizerContext(
            llm, max_tokens=50, summary_threshold=0.5, keep_recent=5
        )

        messages = [
            {"role": "user", "content": "Message 1 with enough content to exceed threshold"},
            {"role": "assistant", "content": "Response 1 with enough content to exceed threshold"},
        ]

        processed, report = await context.process(messages, max_tokens=50)

        assert len(processed) == len(messages)
        assert report.strategy_used == "insufficient_messages"

    @pytest.mark.asyncio
    async def test_token_estimation(self) -> None:
        """Test token estimation."""
        llm = MockLLMProvider()
        context = SummarizerContext(llm)

        messages = [
            {"role": "user", "content": "a" * 400},  # ~100 tokens
        ]

        tokens = context._estimate_tokens(messages)
        assert 90 <= tokens <= 110  # Should be around 100

    @pytest.mark.asyncio
    async def test_summary_caching(self) -> None:
        """Test that summaries are cached."""
        llm = MockLLMProvider()
        context = SummarizerContext(
            llm, max_tokens=100, summary_threshold=0.5, keep_recent=2
        )

        messages = [
            {"role": "user", "content": "Message " + str(i) * 50}
            for i in range(5)
        ]

        # First call
        await context.process(messages, max_tokens=100)
        first_call_count = llm.call_count

        # Second call with same messages
        await context.process(messages, max_tokens=100)
        second_call_count = llm.call_count

        # Should use cache, so call count shouldn't increase
        assert second_call_count == first_call_count


class TestKeyInfoExtractor:
    """Test suite for KeyInfoExtractor."""

    @pytest.mark.asyncio
    async def test_no_extraction_needed(self) -> None:
        """Test that no extraction occurs when under limit."""
        llm = MockLLMProvider()
        extractor = KeyInfoExtractor(llm, max_tokens=1000)

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]

        processed, report = await extractor.process(messages, max_tokens=1000)

        assert len(processed) == len(messages)
        assert report.strategy_used == "none"
        assert llm.call_count == 0

    @pytest.mark.asyncio
    async def test_key_info_extraction(self) -> None:
        """Test that key info is extracted when over limit."""
        llm = MockLLMProvider(
            response="- Important decision: Use Python\n- Requirement: Must be fast"
        )
        extractor = KeyInfoExtractor(llm, max_tokens=100, key_info_tokens=50)

        messages = [
            {"role": "user", "content": "Message " + str(i) * 50}
            for i in range(10)
        ]

        processed, report = await extractor.process(messages, max_tokens=100)

        assert len(processed) < len(messages)
        assert report.strategy_used == "key_info_extraction"
        assert llm.call_count == 1

        # Check for key info message
        key_info_found = any(
            "[Key Information]" in m.get("content", "")
            for m in processed
        )
        assert key_info_found

    @pytest.mark.asyncio
    async def test_preserves_system_messages(self) -> None:
        """Test that system messages are preserved."""
        llm = MockLLMProvider(response="- Key point 1")
        extractor = KeyInfoExtractor(llm, max_tokens=100)

        messages = [
            {"role": "system", "content": "System prompt"}
        ] + [
            {"role": "user", "content": "Message " + str(i) * 50}
            for i in range(5)
        ]

        processed, report = await extractor.process(messages, max_tokens=100)

        # System message should be preserved
        system_msgs = [m for m in processed if m["role"] == "system"]
        assert len(system_msgs) >= 1
        assert any("System prompt" in m["content"] for m in system_msgs)

    @pytest.mark.asyncio
    async def test_selects_recent_messages(self) -> None:
        """Test that most recent messages are selected."""
        llm = MockLLMProvider(response="- Key info")
        extractor = KeyInfoExtractor(llm, max_tokens=200, key_info_tokens=50)

        messages = [
            {"role": "user", "content": f"Old message {i}" + "x" * 100}
            for i in range(5)
        ] + [
            {"role": "user", "content": f"Recent {i}"}
            for i in range(3)
        ]

        processed, report = await extractor.process(messages, max_tokens=200)

        # Recent messages should be included
        contents = [m.get("content", "") for m in processed]
        recent_found = sum(1 for c in contents if "Recent" in c)
        assert recent_found > 0

    @pytest.mark.asyncio
    async def test_key_info_limit(self) -> None:
        """Test that key info is limited to 10 items."""
        llm = MockLLMProvider(
            response="\n".join(f"- Key point {i}" for i in range(20))
        )
        extractor = KeyInfoExtractor(llm, max_tokens=100)

        messages = [
            {"role": "user", "content": "Message " + str(i) * 50}
            for i in range(10)
        ]

        await extractor.process(messages, max_tokens=100)

        # Should keep only 10 most recent
        assert len(extractor._key_info) <= 10

    @pytest.mark.asyncio
    async def test_fallback_extraction(self) -> None:
        """Test fallback extraction when LLM fails."""
        # Mock LLM that raises exception
        class FailingLLM:
            async def generate(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
                raise Exception("LLM failed")

        extractor = KeyInfoExtractor(FailingLLM(), max_tokens=50)

        messages = [
            {"role": "user", "content": "Short message"},
            {"role": "user", "content": "Another short one"},
            {"role": "user", "content": "x" * 200},  # Long message
        ]

        processed, report = await extractor.process(messages, max_tokens=50)

        # Should still work with fallback
        assert len(processed) <= len(messages)
        # Short messages should be in key info
        assert len(extractor._key_info) > 0

    @pytest.mark.asyncio
    async def test_token_estimation(self) -> None:
        """Test token estimation."""
        llm = MockLLMProvider()
        extractor = KeyInfoExtractor(llm)

        messages = [
            {"role": "user", "content": "a" * 400},  # ~100 tokens
        ]

        tokens = extractor._estimate_tokens(messages)
        assert 90 <= tokens <= 110
