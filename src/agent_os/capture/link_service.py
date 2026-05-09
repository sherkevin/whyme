"""Link capture helpers for PRD10 capture endpoints.

The router owns HTTP concerns and database writes; this module owns URL
fetching, text extraction, and small pure transformations. Keeping these
steps here makes `/capture/link` easier to reason about without changing its
external contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_os.integrations.crawler import WebCrawler


@dataclass(slots=True)
class LinkFetchResult:
    url: str
    title: str = ""
    description: str = ""
    text: str = ""
    content_type: str = ""
    links: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.text or self.title or self.description)


async def fetch_link_content(url: str, *, timeout: int = 15) -> LinkFetchResult | None:
    """Fetch a URL and return clean text suitable for LLM enrichment."""

    crawler = WebCrawler(timeout=timeout)
    crawled = await crawler.fetch_page(url)
    if crawled is None:
        return None

    raw_page = str(crawled.get("content") or "")
    content_type = str(crawled.get("content_type") or "")
    if "html" in content_type.lower():
        text = crawler.extract_text_content(raw_page, max_length=16000)
    else:
        text = raw_page.strip()[:16000]

    return LinkFetchResult(
        url=url,
        title=(crawled.get("title") or "").strip(),
        description=(crawled.get("description") or "").strip(),
        text=text,
        content_type=content_type,
        links=list(crawled.get("links") or []),
    )


def build_link_enrichment_content(
    *,
    url: str,
    note: str | None,
    fetched: LinkFetchResult | None,
) -> str:
    """Build the grounded prompt content for link enrichment."""

    seed = (note or "").strip()
    fetched_block = ""
    if fetched is not None:
        fetched_block = fetched.text or fetched.description or ""

    return "\n".join(
        part
        for part in [
            f"URL: {url}",
            f"网页标题: {fetched.title}" if fetched and fetched.title else "",
            f"用户备注: {seed}" if seed else "",
            f"网页正文:\n{fetched_block}" if fetched_block else "",
        ]
        if part
    )


def merge_capture_tags(user_tags: list[str], enrichment_tags: list[str] | None) -> list[str]:
    """Merge user and LLM tags while preserving order and max cardinality."""

    merged: list[str] = []
    for tag in list(user_tags or []) + list(enrichment_tags or []):
        if tag and tag not in merged:
            merged.append(tag)
    return merged[:8]


def link_source_extra(
    *,
    note: str | None,
    fetched: LinkFetchResult,
) -> dict[str, Any]:
    return {
        "note": note,
        "fetched_title": fetched.title,
        "description": fetched.description,
        "content_type": fetched.content_type,
        "text_excerpt": fetched.text[:1000],
    }
