"""LiteLLM-based LLM provider implementation."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from agent_os.core.interfaces import LLMProvider
from agent_os.llm.config import LLMRuntimeConfig, normalize_api_base, resolve_llm_config


class LiteLLMProvider(LLMProvider):
    """LLM provider using LiteLLM for OpenAI-compatible models."""

    def __init__(
        self,
        model: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        """Initialize the LiteLLM provider from explicit args + env.

        All env precedence and DeepSeek defaults live in
        ``agent_os.llm.config`` so feature routers never need to know provider
        variable names.
        """

        self.config: LLMRuntimeConfig = resolve_llm_config(
            model=model,
            api_base=api_base,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.model = self.config.model
        self.api_base = self.config.api_base
        self.api_key = self.config.api_key
        self.temperature = self.config.temperature
        self.max_tokens = self.config.max_tokens

    def _normalize_api_base(self, api_base: str | None) -> str | None:
        """Normalize API base URL for litellm compatibility."""

        return normalize_api_base(api_base)

    def _completion_model(self, model: str | None = None) -> str:
        """Return the LiteLLM model string for the configured endpoint."""

        cfg = resolve_llm_config(
            model=model or self.model,
            api_base=self.api_base,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return cfg.litellm_model

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a completion from the LLM."""

        import litellm

        resolved_model = self._completion_model(kwargs.get("model"))
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

        if self.api_base:
            params["api_base"] = self.api_base
        if self.api_key:
            params["api_key"] = self.api_key

        response = await litellm.acompletion(**params)

        choice = response.choices[0]
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
            "model": self._completion_model(kwargs.get("model")),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "stream": True,
        }

        if tools:
            params["tools"] = tools

        for key, value in kwargs.items():
            if key not in ("temperature", "max_tokens", "model"):
                params[key] = value

        if self.api_base:
            params["api_base"] = self.api_base
        if self.api_key:
            params["api_key"] = self.api_key

        response = await litellm.acompletion(**params)

        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None) or ""
            finish_reason = chunk.choices[0].finish_reason
            if content:
                yield {"content": content, "finish_reason": finish_reason}


__all__ = ["LiteLLMProvider"]
