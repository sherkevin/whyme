"""Tests for ContextManager."""

import pytest

from agent_os.context import SlidingWindowContext


class TestSlidingWindowContext:
    """Test suite for SlidingWindowContext."""

    @pytest.fixture
    def context_manager(self) -> SlidingWindowContext:
        """Create a context manager with default settings."""
        return SlidingWindowContext(max_tokens=1000)

    @pytest.mark.asyncio
    async def test_no_pruning_needed(
        self,
        context_manager: SlidingWindowContext,
    ) -> None:
        """Test when messages fit within the token limit."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        result, report = await context_manager.process(messages)

        assert len(result) == 3
        assert report.pruned_count == 0
        assert report.strategy_used == "sliding_window"

    @pytest.mark.asyncio
    async def test_sliding_window_pruning(
        self,
        context_manager: SlidingWindowContext,
    ) -> None:
        """Test that old messages are pruned when over the limit."""
        # Create many messages that will exceed the token limit
        messages = [
            {"role": "system", "content": "System prompt"},
        ]

        # Add 50 user/assistant pairs with longer content
        for i in range(50):
            messages.append({"role": "user", "content": f"User message {i} " * 50})
            messages.append({"role": "assistant", "content": f"Assistant response {i} " * 50})

        result, report = await context_manager.process(messages)

        # System message should be preserved
        assert any(m.get("role") == "system" for m in result)
        # Some messages should have been pruned
        assert report.pruned_count > 0
        assert len(result) < len(messages)

    @pytest.mark.asyncio
    async def test_system_messages_preserved(self) -> None:
        """Test that system messages are always preserved."""
        context_manager = SlidingWindowContext(max_tokens=50)

        messages = [
            {"role": "system", "content": "Important system instruction"},
            {"role": "user", "content": "Hello " * 100},
            {"role": "assistant", "content": "Response " * 100},
        ]

        result, report = await context_manager.process(messages)

        # System message should still be there
        system_messages = [m for m in result if m.get("role") == "system"]
        assert len(system_messages) == 1
        assert system_messages[0]["content"] == "Important system instruction"

    @pytest.mark.asyncio
    async def test_most_recent_messages_kept(
        self,
        context_manager: SlidingWindowContext,
    ) -> None:
        """Test that the most recent messages are kept."""
        messages = []

        # Add messages with distinctive content
        for i in range(20):
            messages.append({"role": "user", "content": f"Message {i}"})

        result, report = await context_manager.process(messages)

        # Should have the most recent messages at the end
        assert len(result) > 0
        # Last message should be preserved
        assert result[-1]["content"] == "Message 19"

    @pytest.mark.asyncio
    async def test_custom_max_tokens(self) -> None:
        """Test that custom max_tokens override works."""
        context_manager = SlidingWindowContext(max_tokens=1000)

        messages = [
            {"role": "user", "content": "Short"},
            {"role": "assistant", "content": "Response"},
        ]

        # Use a much smaller limit
        result, report = await context_manager.process(messages, max_tokens=10)

        assert report.remaining_tokens <= 10

    @pytest.mark.asyncio
    async def test_empty_messages(self) -> None:
        """Test handling of empty message list."""
        context_manager = SlidingWindowContext()

        result, report = await context_manager.process([])

        assert len(result) == 0
        assert report.pruned_count == 0
        assert report.original_tokens == 0

    @pytest.mark.asyncio
    async def test_report_fields(
        self,
        context_manager: SlidingWindowContext,
    ) -> None:
        """Test that all report fields are populated correctly."""
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Hello " * 100},
            {"role": "assistant", "content": "Hi " * 100},
        ]

        result, report = await context_manager.process(messages)

        assert report.original_tokens > 0
        assert report.remaining_tokens > 0
        assert report.remaining_tokens <= report.original_tokens
        assert report.strategy_used == "sliding_window"
        assert report.summary_content is not None

    @pytest.mark.asyncio
    async def test_multimodal_content(self) -> None:
        """Test handling of multimodal content (list format)."""
        context_manager = SlidingWindowContext(max_tokens=100)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "This is a text message"},
                    {"type": "image_url", "image_url": {"url": "http://example.com/image.png"}},
                ],
            },
        ]

        result, report = await context_manager.process(messages)

        assert len(result) == 1
        assert isinstance(result[0]["content"], list)

    @pytest.mark.asyncio
    async def test_assistant_and_user_only(self) -> None:
        """Test with only assistant and user messages (no system)."""
        context_manager = SlidingWindowContext(max_tokens=100)

        messages = [
            {"role": "user", "content": "First message " * 50},
            {"role": "assistant", "content": "First response " * 50},
            {"role": "user", "content": "Second message"},
            {"role": "assistant", "content": "Second response"},
        ]

        result, report = await context_manager.process(messages)

        # Should keep some messages
        assert len(result) > 0
        # Most recent messages should be preserved
        assert result[-1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_different_approximation_factors(self) -> None:
        """Test with different token approximation factors."""
        # Lower factor means more estimated tokens per char
        context_manager = SlidingWindowContext(
            max_tokens=50,
            approximate_tokens_per_char=0.5,
        )

        messages = [
            {"role": "user", "content": "A" * 100},  # ~50 tokens with this factor
        ]

        result, report = await context_manager.process(messages)

        # Message should fit just at the limit
        assert len(result) == 1
