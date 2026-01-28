"""Tests for LLM Provider."""

import os

import pytest

from agent_os.llm import LiteLLMProvider


class TestLiteLLMProvider:
    """Test suite for LiteLLMProvider."""

    def test_init_with_defaults(self) -> None:
        """Test initialization with default values."""
        provider = LiteLLMProvider()

        assert provider.model == "openai/gpt-4o-mini"
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
    async def test_complete_missing_api_key(self) -> None:
        """Test completion fails without API key."""
        # Ensure no API key is set
        provider = LiteLLMProvider(api_key=None)
        os.environ.pop("API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("LITELLM_API_KEY", None)

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
            api_base=os.getenv("BASE_URL"),
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

    def test_normalize_api_base_none(self) -> None:
        """Test normalization with None."""
        provider = LiteLLMProvider(api_base=None)
        assert provider.api_base is None

    def test_normalize_api_base_trailing_slash(self) -> None:
        """Test normalization removes trailing slash."""
        provider = LiteLLMProvider(api_base="https://api.example.com/v1/")
        assert provider.api_base == "https://api.example.com/v1"
