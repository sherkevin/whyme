"""Model catalog and routing aliases for Mydow AI.

The UI exposes product-friendly names while the runtime may call a different
OpenAI-compatible upstream model. Keep that mapping here so routers, providers,
and settings pages do not each invent their own model semantics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelCatalogItem:
    id: str
    label: str
    vendor: str
    tier: str
    upstream_model: str
    description: str
    enabled: bool
    default: bool = False
    reserved: bool = False
    badge: str = ""
    alias_of: str | None = None
    disabled_reason: str = ""

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "vendor": self.vendor,
            "tier": self.tier,
            "model": self.upstream_model,
            "upstream_model": self.upstream_model,
            "description": self.description,
            "enabled": self.enabled,
            "available": self.enabled,
            "default": self.default,
            "reserved": self.reserved,
            "badge": self.badge,
            "alias_of": self.alias_of,
            "disabled_reason": self.disabled_reason,
        }


MODEL_CATALOG: tuple[ModelCatalogItem, ...] = (
    ModelCatalogItem(
        id="mydow",
        label="Mydow",
        vendor="Mydow",
        tier="pro",
        upstream_model="deepseek-v4-pro",
        description="Mydow 品牌模型，当前路由到 DeepSeek V4 Pro，适合复杂 RAG、长文档和高质量输出。",
        enabled=True,
        default=True,
        badge="Pro",
        alias_of="deepseek-v4-pro",
    ),
    ModelCatalogItem(
        id="deepseek-v4-pro",
        label="DeepSeek V4 Pro",
        vendor="DeepSeek",
        tier="pro",
        upstream_model="deepseek-v4-pro",
        description="DeepSeek V4 Pro，适合复杂推理、长文档总结、知识库问答和高质量写作。",
        enabled=True,
        badge="Pro",
    ),
    ModelCatalogItem(
        id="deepseek-v4-flash",
        label="DeepSeek V4 Flash",
        vendor="DeepSeek",
        tier="fast",
        upstream_model="deepseek-v4-flash",
        description="DeepSeek V4 Flash，适合快速问答、轻量搜索、日常摘要和低延迟交互。",
        enabled=True,
        badge="Fast",
    ),
    ModelCatalogItem(
        id="glm",
        label="GLM",
        vendor="Zhipu",
        tier="reserved",
        upstream_model="glm-4.5",
        description="预留 GLM 供应商入口；配置 GLM_API_KEY/GLM_BASE_URL 后可接入。",
        enabled=False,
        reserved=True,
        badge="预留",
        disabled_reason="GLM 供应商尚未配置，当前不会发起假调用。",
    ),
    ModelCatalogItem(
        id="gemini",
        label="Gemini",
        vendor="Google",
        tier="reserved",
        upstream_model="gemini-2.5-pro",
        description="预留 Gemini 供应商入口；配置 GEMINI_API_KEY 后可接入。",
        enabled=False,
        reserved=True,
        badge="预留",
        disabled_reason="Gemini 供应商尚未配置，当前不会发起假调用。",
    ),
    ModelCatalogItem(
        id="gpt",
        label="GPT",
        vendor="OpenAI",
        tier="reserved",
        upstream_model="gpt-5.2",
        description="预留 GPT 供应商入口；配置 OPENAI_API_KEY 后可接入。",
        enabled=False,
        reserved=True,
        badge="预留",
        disabled_reason="GPT 供应商尚未配置，当前不会发起假调用。",
    ),
)


_BY_ID = {item.id: item for item in MODEL_CATALOG}
_ALIASES: dict[str, str] = {
    "auto": "mydow",
    "mydow-auto": "mydow",
    "mydow auto": "mydow",
    "mydow模型": "mydow",
    "mydow model": "mydow",
    "mydow": "mydow",
    "deepseek-v4-pro": "deepseek-v4-pro",
    "deepseek v4 pro": "deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "deepseek v4 flash": "deepseek-v4-flash",
    "glm": "glm",
    "glm-4": "glm",
    "gemini": "gemini",
    "gemini 2.5 flash": "gemini",
    "gemini 2.5 pro": "gemini",
    "gpt": "gpt",
    "gpt-5.2": "gpt",
    "gpt 5.2": "gpt",
    "opus 4.6": "mydow",
}


def _key(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_model_id(value: str | None) -> str | None:
    key = _key(value)
    if not key:
        return None
    return _ALIASES.get(key, key)


def get_model_item(value: str | None) -> ModelCatalogItem | None:
    model_id = normalize_model_id(value)
    if model_id is None:
        return None
    return _BY_ID.get(model_id)


def default_model_item() -> ModelCatalogItem:
    return next(item for item in MODEL_CATALOG if item.default)


def model_catalog_for_api() -> list[dict[str, Any]]:
    return [item.to_api_dict() for item in MODEL_CATALOG]


def resolve_runtime_model(value: str | None, *, allow_disabled: bool = False) -> str:
    item = get_model_item(value)
    if item is None:
        return (value or "").strip()
    if not item.enabled and not allow_disabled:
        raise ValueError(item.disabled_reason or f"Model {item.label} is not enabled")
    return item.upstream_model


def resolve_chat_model(value: str | None) -> ModelCatalogItem:
    item = get_model_item(value) or default_model_item()
    if not item.enabled:
        raise ValueError(item.disabled_reason or f"Model {item.label} is not enabled")
    return item


__all__ = [
    "MODEL_CATALOG",
    "ModelCatalogItem",
    "default_model_item",
    "get_model_item",
    "model_catalog_for_api",
    "normalize_model_id",
    "resolve_chat_model",
    "resolve_runtime_model",
]
