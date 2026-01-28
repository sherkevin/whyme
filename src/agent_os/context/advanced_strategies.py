"""Summarizer context manager for compressing conversation history.

This module provides a context manager that uses LLM to summarize
older messages when the context window is getting full.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from agent_os.core.interfaces import ContextManager, LLMProvider
from agent_os.core.types import PruningReport


class SummarizerContext(ContextManager):
    """Context manager that summarizes old messages to save tokens.

    This strategy keeps recent messages intact and summarizes older
    messages into a condensed format when approaching token limits.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        max_tokens: int = 8000,
        summary_threshold: float = 0.7,
        keep_recent: int = 5,
    ) -> None:
        """Initialize the summarizer context manager.

        Args:
            llm_provider: LLM provider for generating summaries
            max_tokens: Maximum tokens to keep in context
            summary_threshold: Trigger summarization at this % of max_tokens
            keep_recent: Number of recent messages to keep unsummarized
        """
        self.llm_provider = llm_provider
        self.max_tokens = max_tokens
        self.summary_threshold = summary_threshold
        self.keep_recent = keep_recent
        self._summary_cache: Dict[str, str] = {}

    async def process(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
    ) -> Tuple[List[Dict[str, Any]], PruningReport]:
        """Process messages with summarization.

        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens allowed

        Returns:
            Tuple of (processed messages, pruning report)
        """
        # Estimate token count (rough approximation)
        total_tokens = self._estimate_tokens(messages)

        # Check if summarization is needed
        threshold_tokens = int(max_tokens * self.summary_threshold)

        if total_tokens <= threshold_tokens:
            # No summarization needed
            return messages, PruningReport(
                original_tokens=total_tokens,
                remaining_tokens=total_tokens,
                pruned_count=0,
                strategy_used="none",
            )

        # Split messages into old and recent
        if len(messages) <= self.keep_recent:
            # Not enough messages to summarize
            return messages, PruningReport(
                original_tokens=total_tokens,
                remaining_tokens=total_tokens,
                pruned_count=0,
                strategy_used="insufficient_messages",
            )

        # Keep system message if present
        system_messages = [m for m in messages if m.get("role") == "system"]
        non_system_messages = [m for m in messages if m.get("role") != "system"]

        # Split into old and recent
        old_messages = non_system_messages[: -self.keep_recent]
        recent_messages = non_system_messages[-self.keep_recent :]

        # Generate summary of old messages
        summary = await self._generate_summary(old_messages)

        # Create summary message
        summary_message = {
            "role": "system",
            "content": f"[Previous conversation summary]\n{summary}",
        }

        # Combine: system + summary + recent
        processed = system_messages + [summary_message] + recent_messages

        # Calculate tokens saved
        old_tokens = self._estimate_tokens(old_messages)
        summary_tokens = self._estimate_tokens([summary_message])
        tokens_saved = old_tokens - summary_tokens
        remaining_tokens = self._estimate_tokens(processed)

        return processed, PruningReport(
            original_tokens=total_tokens,
            remaining_tokens=remaining_tokens,
            pruned_count=len(messages) - len(processed),
            strategy_used="summarization",
        )

    async def _generate_summary(self, messages: List[Dict[str, Any]]) -> str:
        """Generate a summary of messages using LLM.

        Args:
            messages: Messages to summarize

        Returns:
            Summary text
        """
        # Create cache key
        cache_key = self._create_cache_key(messages)
        if cache_key in self._summary_cache:
            return self._summary_cache[cache_key]

        # Format messages for summarization
        conversation_text = self._format_messages(messages)

        # Create summarization prompt
        summary_prompt = f"""Summarize the following conversation concisely, preserving key information, decisions, and context:

{conversation_text}

Provide a brief summary (2-3 paragraphs) that captures:
1. Main topics discussed
2. Important decisions or conclusions
3. Relevant context for future messages

Summary:"""

        # Generate summary
        try:
            response = await self.llm_provider.generate(
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=500,
                temperature=0.3,
            )

            summary = response.get("content", "")

            # Cache the summary
            self._summary_cache[cache_key] = summary

            return summary
        except Exception as e:
            # Fallback: simple concatenation
            return f"Previous conversation covered: {self._extract_topics(messages)}"

    def _format_messages(self, messages: List[Dict[str, Any]]) -> str:
        """Format messages as text for summarization."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role.upper()}: {content}")
        return "\n\n".join(lines)

    def _extract_topics(self, messages: List[Dict[str, Any]]) -> str:
        """Extract simple topic list from messages (fallback)."""
        topics = []
        for msg in messages:
            content = msg.get("content", "")
            # Extract first sentence or first 50 chars
            first_part = content.split(".")[0][:50]
            if first_part and first_part not in topics:
                topics.append(first_part)
        return ", ".join(topics[:5])

    def _create_cache_key(self, messages: List[Dict[str, Any]]) -> str:
        """Create a cache key for messages."""
        # Simple hash based on message count and first/last content
        if not messages:
            return "empty"
        first = messages[0].get("content", "")[:20]
        last = messages[-1].get("content", "")[:20]
        return f"{len(messages)}:{first}:{last}"

    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate token count for messages.

        Uses rough approximation: 1 token ≈ 4 characters.
        """
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            total_chars += len(content)
        return total_chars // 4


class KeyInfoExtractor(ContextManager):
    """Context manager that extracts and preserves key information.

    This strategy identifies important information (decisions, facts,
    requirements) and ensures they are preserved in the context.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        max_tokens: int = 8000,
        key_info_tokens: int = 1000,
    ) -> None:
        """Initialize the key info extractor.

        Args:
            llm_provider: LLM provider for extraction
            max_tokens: Maximum tokens to keep
            key_info_tokens: Tokens reserved for key information
        """
        self.llm_provider = llm_provider
        self.max_tokens = max_tokens
        self.key_info_tokens = key_info_tokens
        self._key_info: List[str] = []

    async def process(
        self,
        messages: List[Dict[str, Any]],
        max_tokens: int,
    ) -> Tuple[List[Dict[str, Any]], PruningReport]:
        """Process messages with key info extraction.

        Args:
            messages: List of message dictionaries
            max_tokens: Maximum tokens allowed

        Returns:
            Tuple of (processed messages, pruning report)
        """
        # Estimate tokens
        total_tokens = self._estimate_tokens(messages)

        if total_tokens <= max_tokens:
            return messages, PruningReport(
                original_tokens=total_tokens,
                remaining_tokens=total_tokens,
                pruned_count=0,
                strategy_used="none",
            )

        # Extract key information from older messages
        await self._extract_key_info(messages)

        # Keep system messages
        system_messages = [m for m in messages if m.get("role") == "system"]

        # Calculate how many recent messages we can keep
        available_tokens = max_tokens - self.key_info_tokens
        recent_messages = self._select_recent_messages(messages, available_tokens)

        # Create key info message
        if self._key_info:
            key_info_message = {
                "role": "system",
                "content": "[Key Information]\n" + "\n".join(f"- {info}" for info in self._key_info),
            }
            processed = system_messages + [key_info_message] + recent_messages
        else:
            processed = system_messages + recent_messages

        tokens_saved = total_tokens - self._estimate_tokens(processed)
        remaining_tokens = self._estimate_tokens(processed)

        return processed, PruningReport(
            original_tokens=total_tokens,
            remaining_tokens=remaining_tokens,
            pruned_count=len(messages) - len(processed),
            strategy_used="key_info_extraction",
        )

    async def _extract_key_info(self, messages: List[Dict[str, Any]]) -> None:
        """Extract key information from messages."""
        # Format messages
        conversation_text = self._format_messages(messages)

        # Create extraction prompt
        extraction_prompt = f"""Extract key information from this conversation. Focus on:
1. Important decisions made
2. Requirements or specifications
3. Critical facts or data
4. Action items or next steps

Conversation:
{conversation_text}

List key information as bullet points (max 10 items):"""

        try:
            response = await self.llm_provider.generate(
                messages=[{"role": "user", "content": extraction_prompt}],
                max_tokens=300,
                temperature=0.2,
            )

            content = response.get("content", "")

            # Parse bullet points
            lines = content.strip().split("\n")
            for line in lines:
                line = line.strip()
                if line.startswith("-") or line.startswith("•"):
                    info = line[1:].strip()
                    if info and info not in self._key_info:
                        self._key_info.append(info)

            # Keep only most recent key info
            self._key_info = self._key_info[-10:]

        except Exception:
            # Fallback: extract from user messages
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    if len(content) < 100:  # Short messages likely important
                        if content not in self._key_info:
                            self._key_info.append(content)

    def _select_recent_messages(
        self,
        messages: List[Dict[str, Any]],
        available_tokens: int,
    ) -> List[Dict[str, Any]]:
        """Select recent messages that fit in available tokens."""
        non_system = [m for m in messages if m.get("role") != "system"]

        # Start from most recent and work backwards
        selected = []
        tokens_used = 0

        for msg in reversed(non_system):
            msg_tokens = self._estimate_tokens([msg])
            if tokens_used + msg_tokens <= available_tokens:
                selected.insert(0, msg)
                tokens_used += msg_tokens
            else:
                break

        return selected

    def _format_messages(self, messages: List[Dict[str, Any]]) -> str:
        """Format messages as text."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            lines.append(f"{role.upper()}: {content}")
        return "\n\n".join(lines)

    def _estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate token count (1 token ≈ 4 characters)."""
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return total_chars // 4
