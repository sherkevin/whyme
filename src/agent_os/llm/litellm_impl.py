"""LiteLLM-based LLM provider implementation."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

from agent_os.core.interfaces import LLMProvider


class LiteLLMProvider(LLMProvider):
    """LLM provider using LiteLLM for multi-model support."""

    def __init__(
        self,
        model: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        """Initialize the LiteLLM provider.

        Args:
            model: Model identifier (e.g., "deepseek-v4-flash", "anthropic/claude-3-haiku")
            api_base: Optional API base URL (e.g., "https://api.example.com/v1")
            api_key: Optional API key (defaults to environment variable)
            temperature: Default sampling temperature
            max_tokens: Default max tokens
        """
        self.model = (
            model
            or os.getenv("AGENTOS_AI_MODEL")
            or os.getenv("LLM_MODEL")
            or os.getenv("MODEL")
            or os.getenv("DEEPSEEK_MODEL")
            or "deepseek-v4-flash"
        )
        # Normalize API base URL (remove trailing /chat/ if present).
        #
        # §15.43 — `API_BASE` is the canonical LLM endpoint env (it ships
        # with the paratera key). `BASE_URL` is the *application's own*
        # public URL used by docker-compose / nginx, so accepting it as
        # an LLM endpoint silently routes calls back at our own server
        # and yields a useless 404. Try the LLM-specific names first,
        # then fall back to BASE_URL only when none of them are set
        # (this preserves the legacy single-env-var workflow without
        # breaking the standard setup).
        self.api_base = self._normalize_api_base(
            api_base
            or os.getenv("API_BASE")
            or os.getenv("DEEPSEEK_OPENAI_BASE_URL")
            or os.getenv("LITELLM_API_BASE")
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("BASE_URL")
        )
        self.api_key = (
            api_key
            or os.getenv("API_KEY")
            or os.getenv("LITELLM_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
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
        if base.endswith("/chat") or base.endswith("/v1/chat"):
            base = base[:-5]
        return base

    def _completion_model(self) -> str:
        """Return the LiteLLM model string for the configured endpoint.

        DeepSeek's new model names are served through an OpenAI-compatible
        endpoint but are not always present in LiteLLM's provider model list.
        Prefixing with ``openai/`` selects the generic OpenAI-compatible
        adapter while preserving the actual model name sent to the API.
        """

        if "/" in self.model:
            return self.model
        if self.api_base:
            return f"openai/{self.model}"
        return self.model

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a completion from the LLM."""
        import litellm

        override_model = kwargs.get("model")
        if override_model:
            saved_model = self.model
            try:
                self.model = override_model
                resolved_model = self._completion_model()
            finally:
                self.model = saved_model
        else:
            resolved_model = self._completion_model()

        params = {
            "model": resolved_model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        if tools:
            params["tools"] = tools

        for key, value in kwargs.items():
            if key not in ("temperature", "max_tokens", "model"):
                params[key] = value

        # Set API base and key for this specific call
        if self.api_base:
            params["api_base"] = self.api_base
        if self.api_key:
            params["api_key"] = self.api_key

        response = await litellm.acompletion(**params)

        # Parse response
        choice = response.choices[0]
        # Reasoning-mode models can return private reasoning_content before
        # the final answer. Never expose reasoning_content as user-facing
        # text; callers treat reasoning-only output as a real provider
        # failure and ask for more budget / a valid non-reasoning response.
        primary_content = (choice.message.content or "").strip()
        reasoning_content = (
            getattr(choice.message, "reasoning_content", None) or ""
        ).strip()
        content = primary_content

        result = {
            "content": content,
            "role": choice.message.role,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
        }
        if reasoning_content:
            result["reasoning"] = reasoning_content
            if not primary_content:
                result["reasoning_only"] = True

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
            "model": self._completion_model(),
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

        # Reasoning-mode SSE streams may emit `reasoning_content` deltas
        # before final `content` deltas. Do not surface private reasoning to
        # the UI; only yield final answer content.
        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None) or ""
            finish_reason = chunk.choices[0].finish_reason
            if content:
                yield {"content": content, "finish_reason": finish_reason}


__all__ = ["LiteLLMProvider"]
