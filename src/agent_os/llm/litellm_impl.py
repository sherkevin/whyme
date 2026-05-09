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
        # Reasoning-mode models (DeepSeek v4-pro/v4-flash in reasoner mode,
        # GLM-Z1, etc.) put their visible answer in `reasoning_content` and
        # leave `content` empty when `max_tokens` is exhausted by the
        # chain-of-thought. Fall back to reasoning_content so the Mydow AI
        # workspace always shows the user something rather than a blank
        # bubble. Strip surrounding whitespace; if both are empty we keep
        # an empty string so the caller can show the configured fallback
        # placeholder.
        primary_content = (choice.message.content or "").strip()
        reasoning_content = (
            getattr(choice.message, "reasoning_content", None) or ""
        ).strip()
        if primary_content:
            content = primary_content
        elif reasoning_content:
            # Prefix so it's clear this is the reasoning trace; non-reasoning
            # models never reach this branch so production demos stay clean.
            content = "（思考过程）" + reasoning_content
        else:
            content = ""

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
        if reasoning_content and primary_content:
            result["reasoning"] = reasoning_content

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

        # Same content/reasoning_content fallback logic as ``complete``.
        # Reasoning-mode SSE streams emit `reasoning_content` deltas first,
        # then switch to `content` deltas once the model finalizes its
        # answer. We surface BOTH to the caller so the AI workspace can
        # show "正在思考…" for reasoning chunks and append the actual
        # answer naturally as it arrives. Non-reasoning models never emit
        # ``reasoning_content`` and behave exactly as before.
        seen_real_content = False
        async for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None) or ""
            reasoning_delta = getattr(delta, "reasoning_content", None) or ""
            finish_reason = chunk.choices[0].finish_reason
            if content:
                seen_real_content = True
                yield {"content": content, "finish_reason": finish_reason}
                continue
            # Only forward reasoning chunks if the model never emitted
            # any visible content — this prevents reasoning text from
            # contaminating the final answer when both are present.
            if reasoning_delta and not seen_real_content:
                yield {
                    "content": reasoning_delta,
                    "kind": "reasoning",
                    "finish_reason": finish_reason,
                }


__all__ = ["LiteLLMProvider"]
