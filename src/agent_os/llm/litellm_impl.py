"""LiteLLM-based LLM provider implementation."""

from __future__ import annotations

import os
from typing import Any, AsyncIterator

from agent_os.core.interfaces import LLMProvider


class LiteLLMProvider(LLMProvider):
    """LLM provider using LiteLLM for multi-model support."""

    def __init__(
        self,
        model: str = "openai/gpt-4o-mini",
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        """Initialize the LiteLLM provider.

        Args:
            model: Model identifier (e.g., "openai/gpt-4o-mini", "anthropic/claude-3-haiku")
            api_base: Optional API base URL (e.g., "https://api.example.com/v1")
            api_key: Optional API key (defaults to environment variable)
            temperature: Default sampling temperature
            max_tokens: Default max tokens
        """
        self.model = model
        # Normalize API base URL (remove trailing /chat/ if present)
        self.api_base = self._normalize_api_base(api_base)
        self.api_key = api_key or os.getenv("API_KEY") or os.getenv("LITELLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Set environment variables for litellm
        if self.api_key:
            os.environ["LITELLM_API_KEY"] = self.api_key
            os.environ["OPENAI_API_KEY"] = self.api_key

    def _normalize_api_base(self, api_base: str | None) -> str | None:
        """Normalize API base URL for litellm compatibility."""
        if not api_base:
            return None

        # Remove trailing /chat/ or /chat if present
        # litellm expects base URL like "https://api.example.com/v1"
        base = api_base.rstrip("/")
        if base.endswith("/chat"):
            base = base[:-5]
        elif base.endswith("/v1/chat"):
            base = base[:-5]
        return base

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a completion from the LLM."""
        import litellm

        # Merge default kwargs with provided ones
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        if tools:
            params["tools"] = tools

        # Add any additional parameters
        for key, value in kwargs.items():
            if key not in ("temperature", "max_tokens"):
                params[key] = value

        # Set API base and key for this specific call
        if self.api_base:
            params["api_base"] = self.api_base
        if self.api_key:
            params["api_key"] = self.api_key

        response = await litellm.acompletion(**params)

        # Parse response
        choice = response.choices[0]
        result = {
            "content": choice.message.content or "",
            "role": choice.message.role,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
        }

        # Add tool calls if present
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return result

    async def stream_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream completions from the LLM."""
        import litellm

        params = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": True,
        }

        if tools:
            params["tools"] = tools

        if self.api_base:
            params["api_base"] = self.api_base
        if self.api_key:
            params["api_key"] = self.api_key

        response = await litellm.acompletion(**params)

        async for chunk in response:
            if chunk.choices:
                delta = chunk.choices[0].delta
                content = delta.content if hasattr(delta, "content") else ""
                if content:
                    yield {
                        "content": content,
                        "finish_reason": chunk.choices[0].finish_reason,
                    }


__all__ = ["LiteLLMProvider"]
