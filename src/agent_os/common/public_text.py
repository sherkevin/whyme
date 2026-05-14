"""Utilities for text that is rendered to end users."""

from __future__ import annotations

import re


_PUBLIC_TEXT_REPLACEMENTS = (
    ("[seed]", ""),
    (" 的精炼摘要——演示用。", " 的精炼摘要。"),
    ("的精炼摘要——演示用。", "的精炼摘要。"),
    ("——演示用", ""),
    ("演示用", ""),
    ("PRD10 演示文档", "PRD10 文档"),
    ("PRD10 演示资料", "PRD10 资料"),
    ("PRD10 演示数据", "PRD10 基线数据"),
)


def sanitize_public_text(value: str | None) -> str | None:
    """Remove internal seed/demo markers before text reaches the product UI."""

    if value is None:
        return None
    text = str(value)
    for source, replacement in _PUBLIC_TEXT_REPLACEMENTS:
        text = text.replace(source, replacement)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([，。！？；：])", r"\1", text)
    return text
