"""Sliding window context manager implementation."""

from __future__ import annotations

from typing import Any

from agent_os.core.interfaces import ContextManager
from agent_os.core.types import PruningReport


class SlidingWindowContext(ContextManager):
    """Context manager that uses a sliding window strategy.

    This implementation keeps the most recent messages within the token limit,
    discarding older messages as needed. It always preserves system messages.
    """

    def __init__(self, max_tokens: int = 8000, approximate_tokens_per_char: float = 0.25) -> None:
        """Initialize the sliding window context manager.

        Args:
            max_tokens: Maximum number of tokens to keep in context.
            approximate_tokens_per_char: Approximate number of tokens per character
                for estimating token count without actually tokenizing.
        """
        self.max_tokens = max_tokens
        self.approximate_tokens_per_char = approximate_tokens_per_char

    def _estimate_tokens(self, text: str) -> int:
        """Estimate the number of tokens in a text string."""
        # Rough approximation: ~4 characters per token for English text
        return int(len(text) * self.approximate_tokens_per_char)

    def _estimate_message_tokens(self, message: dict[str, Any]) -> int:
        """Estimate tokens in a message."""
        # Estimate based on content string
        content = message.get("content", "")
        if isinstance(content, str):
            return self._estimate_tokens(content)
        elif isinstance(content, list):
            # Handle multimodal content
            total = 0
            for item in content:
                if isinstance(item, dict):
                    total += self._estimate_tokens(str(item.get("text", "")))
            return total
        return self._estimate_tokens(str(content))

    async def process(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
    ) -> tuple[list[dict[str, Any]], PruningReport]:
        """Process messages using sliding window strategy.

        This method:
        1. Always preserves system messages (role="system")
        2. Keeps the most recent user/assistant messages within the token limit
        3. Returns a report of what was pruned

        Args:
            messages: Input messages to process
            max_tokens: Override the default max_tokens for this call

        Returns:
            A tuple of (processed_messages, pruning_report)
        """
        limit = max_tokens or self.max_tokens

        # Separate system messages from regular messages
        system_messages: list[dict[str, Any]] = [
            m for m in messages if m.get("role") == "system"
        ]
        regular_messages: list[dict[str, Any]] = [
            m for m in messages if m.get("role") != "system"
        ]

        # Calculate original token count
        original_tokens = sum(
            self._estimate_message_tokens(m) for m in messages
        )

        # Calculate system message tokens
        system_tokens = sum(
            self._estimate_message_tokens(m) for m in system_messages
        )

        # Calculate available tokens for regular messages
        available_tokens = limit - system_tokens

        # Build result list, starting with system messages
        result: list[dict[str, Any]] = list(system_messages)

        # Add regular messages from most recent to oldest until we hit the limit
        # We iterate in reverse and build up
        kept_regular: list[dict[str, Any]] = []
        current_tokens = 0

        for message in reversed(regular_messages):
            msg_tokens = self._estimate_message_tokens(message)

            if current_tokens + msg_tokens <= available_tokens:
                kept_regular.insert(0, message)
                current_tokens += msg_tokens
            else:
                # This message would exceed the limit
                break

        result.extend(kept_regular)

        # Calculate remaining tokens
        remaining_tokens = sum(
            self._estimate_message_tokens(m) for m in result
        )

        # Create report
        pruned_count = len(messages) - len(result)

        report = PruningReport(
            original_tokens=original_tokens,
            remaining_tokens=remaining_tokens,
            pruned_count=pruned_count,
            strategy_used="sliding_window",
            summary_content=f"Kept {len(result)} of {len(messages)} messages using sliding window",
        )

        return result, report


__all__ = ["SlidingWindowContext"]
