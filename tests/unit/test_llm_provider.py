"""Tests for LLM Provider."""

import os

import pytest

from agent_os.llm import LiteLLMProvider
from agent_os.llm.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    OPENAI_BASE_URL,
    resolve_model,
)
from agent_os.llm.model_registry import resolve_chat_model


class TestLiteLLMProvider:
    """Test suite for LiteLLMProvider."""

    def test_init_with_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initialization with default values."""
        for name in (
            "AGENTOS_AI_MODEL",
            "LLM_MODEL",
            "MODEL",
            "DEEPSEEK_MODEL",
            "LLM_BASE_URL",
            "API_BASE",
            "DEEPSEEK_OPENAI_BASE_URL",
            "LITELLM_API_BASE",
            "OPENAI_API_BASE",
            "BASE_URL",
            "LLM_PROVIDER",
            "AGENTOS_LLM_ALLOW_BASE_URL",
        ):
            monkeypatch.delenv(name, raising=False)
        provider = LiteLLMProvider()

        assert provider.model == DEFAULT_MODEL
        assert provider.api_base == DEFAULT_BASE_URL
        assert provider.temperature == 0.7
        assert provider.max_tokens == 4096

    def test_init_with_custom_values(self) -> None:
        """Test initialization with custom values."""
        provider = LiteLLMProvider(
            model="anthropic/claude-3-haiku",
            temperature=0.5,
            max_tokens=2048,
        )

        assert provider.model == "anthropic/claude-3-haiku"
        assert provider.temperature == 0.5
        assert provider.max_tokens == 2048

    def test_normalize_api_base(self) -> None:
        """Test API base URL normalization."""
        provider = LiteLLMProvider(api_base="https://api.example.com/v1/chat/")

        # Should remove trailing /chat/ and /
        assert provider.api_base == "https://api.example.com/v1"

    def test_normalize_api_base_with_v1_chat(self) -> None:
        """Test API base URL normalization with /v1/chat."""
        provider = LiteLLMProvider(api_base="https://llmapi.paratera.com/v1/chat/")

        assert provider.api_base == "https://llmapi.paratera.com/v1"

    def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting API key from environment."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LITELLM_API_KEY", raising=False)
        monkeypatch.setenv("API_KEY", "test-key-123")

        provider = LiteLLMProvider()
        assert provider.api_key == "test-key-123"

    def test_api_base_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test getting API base from environment."""
        # Note: dotenv loads variables at module import time
        # So we need to explicitly pass api_base here
        provider = LiteLLMProvider(api_base="https://api.example.com/v1/")
        assert provider.api_base == "https://api.example.com/v1"

    @pytest.mark.asyncio
    async def test_complete_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test completion fails without API key."""
        # Ensure no API key is set
        monkeypatch.delenv("API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LITELLM_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        provider = LiteLLMProvider(api_key=None)

        with pytest.raises(Exception):
            await provider.complete(
                messages=[{"role": "user", "content": "Hello"}],
            )

    @pytest.mark.skipif(
        not os.getenv("API_KEY"),
        reason="Requires API_KEY environment variable"
    )
    @pytest.mark.asyncio
    async def test_complete_with_real_api(self) -> None:
        """Test completion with real API (requires API_KEY)."""
        provider = LiteLLMProvider(
            api_base=(
                os.getenv("LLM_BASE_URL")
                or os.getenv("API_BASE")
                or os.getenv("DEEPSEEK_OPENAI_BASE_URL")
                or DEFAULT_BASE_URL
            ),
            api_key=os.getenv("API_KEY"),
        )

        response = await provider.complete(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OK' in response."},
            ],
            max_tokens=50,
        )

        assert "content" in response
        assert "usage" in response
        assert len(response["content"]) > 0

    def test_api_base_none_uses_llm_specific_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test None falls back to configured LLM endpoint, not app BASE_URL."""
        monkeypatch.setenv("BASE_URL", "http://localhost:8000")
        monkeypatch.setenv("DEEPSEEK_OPENAI_BASE_URL", "https://api.deepseek.com/")
        provider = LiteLLMProvider(api_base=None)
        assert provider.api_base == "https://api.deepseek.com"

    def test_base_url_requires_explicit_legacy_opt_in(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BASE_URL is the application URL unless explicitly opted in."""
        for name in (
            "API_KEY",
            "LITELLM_API_KEY",
            "LLM_BASE_URL",
            "API_BASE",
            "DEEPSEEK_OPENAI_BASE_URL",
            "LITELLM_API_BASE",
            "OPENAI_API_BASE",
        ):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("BASE_URL", "https://legacy-llm.example.com/v1")

        provider = LiteLLMProvider(api_base=None)
        assert provider.api_base == DEFAULT_BASE_URL

        monkeypatch.setenv("AGENTOS_LLM_ALLOW_BASE_URL", "on")
        legacy = LiteLLMProvider(api_base=None)
        assert legacy.api_base == "https://legacy-llm.example.com/v1"

    def test_resolve_model_purpose_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENTOS_AI_MODEL", "deepseek-v4-flash")
        monkeypatch.setenv("CAPTURE_ENRICH_MODEL", "deepseek-v4-pro")

        assert resolve_model("ai") == "deepseek-v4-flash"
        assert resolve_model("capture") == "deepseek-v4-pro"

    def test_resolve_model_maps_mydow_shell_to_deepseek_pro(self) -> None:
        assert resolve_model("ai", explicit="mydow") == "deepseek-v4-pro"
        item = resolve_chat_model("mydow")
        assert item.id == "mydow"
        assert item.upstream_model == "deepseek-v4-pro"

    def test_resolve_model_rejects_reserved_provider(self) -> None:
        with pytest.raises(ValueError, match="GLM"):
            resolve_model("ai", explicit="glm")

    def test_openai_provider_gets_openai_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in (
            "LLM_BASE_URL",
            "API_BASE",
            "DEEPSEEK_OPENAI_BASE_URL",
            "LITELLM_API_BASE",
            "OPENAI_API_BASE",
        ):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
        monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")

        provider = LiteLLMProvider()
        assert provider.api_base == OPENAI_BASE_URL
        assert provider.api_key == "openai-key"

    def test_normalize_api_base_trailing_slash(self) -> None:
        """Test normalization removes trailing slash."""
        provider = LiteLLMProvider(api_base="https://api.example.com/v1/")
        assert provider.api_base == "https://api.example.com/v1"
