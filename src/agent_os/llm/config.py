"""Central LLM provider configuration.

All OpenAI-compatible providers should resolve keys, base URLs, model names,
timeouts, and purpose-specific overrides here. This keeps DeepSeek defaults
and future provider switches out of feature routers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from agent_os.llm.model_registry import resolve_runtime_model


DEFAULT_PROVIDER = "deepseek"
DEFAULT_BASE_URL = "https://api.deepseek.com"
OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_FALLBACK_MODEL = "deepseek-v4-pro"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 1000


_PURPOSE_MODEL_ENV: dict[str, tuple[str, ...]] = {
    "ai": ("AGENTOS_AI_MODEL",),
    "capture": ("CAPTURE_ENRICH_MODEL", "AGENTOS_CAPTURE_MODEL"),
    "skill": ("AGENTOS_SKILL_MODEL",),
    "research": ("AGENTOS_RESEARCH_MODEL",),
    "summary": ("AGENTOS_SUMMARY_MODEL",),
}


@dataclass(frozen=True)
class LLMRuntimeConfig:
    """Resolved runtime configuration for one LLM call family."""

    provider: str
    api_key: str | None
    api_base: str
    model: str
    fallback_model: str
    temperature: float
    max_tokens: int

    @property
    def litellm_model(self) -> str:
        """Model string to hand to LiteLLM.

        DeepSeek v4 model names are served by an OpenAI-compatible endpoint
        but may not exist in LiteLLM's provider registry. Prefixing with
        ``openai/`` forces the generic compatible adapter while preserving the
        actual model sent to the upstream API.
        """

        if "/" in self.model:
            return self.model
        if self.api_base:
            return f"openai/{self.model}"
        return self.model

    def safe_dict(self) -> dict[str, str | int | float | bool | None]:
        """Return non-secret details for logs and health responses."""

        return {
            "provider": self.provider,
            "api_base": self.api_base,
            "model": self.model,
            "fallback_model": self.fallback_model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "has_api_key": bool(self.api_key),
        }


def _env_first(*names: str) -> str | None:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return None


def _parse_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None and value.strip() else default
    except (TypeError, ValueError):
        return default


def _parse_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value) if value is not None and value.strip() else default
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def normalize_api_base(api_base: str | None) -> str | None:
    """Normalize OpenAI-compatible base URLs for LiteLLM."""

    if not api_base:
        return None
    base = api_base.strip().rstrip("/")
    for suffix in ("/chat/completions", "/v1/chat/completions", "/chat", "/v1/chat"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return base.rstrip("/") or None


def _legacy_base_url_if_explicitly_allowed() -> str | None:
    """Support legacy BASE_URL-as-LLM-base only with an explicit opt-in.

    ``BASE_URL`` is the app's public URL in current Docker/deployment docs.
    Treating it as an LLM endpoint silently routes LLM calls back to our own
    server. Use ``LLM_BASE_URL`` / ``API_BASE`` for LLMs; this shim exists only
    for old local scripts that intentionally set ``BASE_URL`` to a provider.
    """

    allow = (os.getenv("AGENTOS_LLM_ALLOW_BASE_URL") or "").strip().lower()
    if allow in {"1", "on", "true", "yes"}:
        return _env_first("BASE_URL")
    return None


def resolve_provider(explicit: str | None = None) -> str:
    return (explicit or _env_first("LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()


def resolve_api_key(
    explicit: str | None = None,
    *,
    provider: str | None = None,
) -> str | None:
    if explicit:
        return explicit
    provider_name = resolve_provider(provider)
    if provider_name == "openai":
        return _env_first(
            "OPENAI_API_KEY",
            "API_KEY",
            "LITELLM_API_KEY",
            "DEEPSEEK_API_KEY",
        )
    return _env_first(
        "DEEPSEEK_API_KEY",
        "API_KEY",
        "LITELLM_API_KEY",
        "OPENAI_API_KEY",
    )


def resolve_api_base(
    explicit: str | None = None,
    *,
    provider: str | None = None,
) -> str:
    provider_name = resolve_provider(provider)
    default_base = OPENAI_BASE_URL if provider_name == "openai" else DEFAULT_BASE_URL
    return normalize_api_base(
        explicit
        or _env_first(
            "LLM_BASE_URL",
            "API_BASE",
            "DEEPSEEK_OPENAI_BASE_URL",
            "LITELLM_API_BASE",
            "OPENAI_API_BASE",
        )
        or _legacy_base_url_if_explicitly_allowed()
        or default_base
    ) or default_base


def resolve_model(purpose: str | None = None, explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return resolve_runtime_model(explicit.strip(), allow_disabled=False)
    purpose_key = (purpose or "").strip().lower()
    purpose_names = _PURPOSE_MODEL_ENV.get(purpose_key, ())
    raw = (
        _env_first(
            *purpose_names,
            "AGENTOS_AI_MODEL",
            "LLM_MODEL",
            "MODEL",
            "DEEPSEEK_MODEL",
        )
        or DEFAULT_MODEL
    )
    return resolve_runtime_model(raw, allow_disabled=False)


def resolve_fallback_model(explicit: str | None = None) -> str:
    return explicit or _env_first(
        "LLM_MODEL_FALLBACK",
        "MODEL_FALLBACK",
        "DEEPSEEK_MODEL_FALLBACK",
    ) or DEFAULT_FALLBACK_MODEL


def resolve_llm_config(
    *,
    purpose: str | None = None,
    provider: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    model: str | None = None,
    fallback_model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> LLMRuntimeConfig:
    """Resolve a call family's LLM config from explicit args + env."""

    temp_default = _parse_float(os.getenv("AGENTOS_AI_TEMPERATURE"), DEFAULT_TEMPERATURE)
    token_default = _parse_int(os.getenv("AGENTOS_AI_MAX_TOKENS"), DEFAULT_MAX_TOKENS)
    provider_name = resolve_provider(provider)
    return LLMRuntimeConfig(
        provider=provider_name,
        api_key=resolve_api_key(api_key, provider=provider_name),
        api_base=resolve_api_base(api_base, provider=provider_name),
        model=resolve_model(purpose, model),
        fallback_model=resolve_fallback_model(fallback_model),
        temperature=float(temperature if temperature is not None else temp_default),
        max_tokens=int(max_tokens if max_tokens is not None else token_default),
    )


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_FALLBACK_MODEL",
    "DEFAULT_MODEL",
    "DEFAULT_PROVIDER",
    "LLMRuntimeConfig",
    "OPENAI_BASE_URL",
    "normalize_api_base",
    "resolve_api_base",
    "resolve_api_key",
    "resolve_fallback_model",
    "resolve_llm_config",
    "resolve_model",
    "resolve_provider",
]
