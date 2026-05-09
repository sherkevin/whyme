"""Link capture helpers for PRD10 capture endpoints.

The router owns HTTP concerns and database writes; this module owns URL
fetching, text extraction, and small pure transformations. Keeping these
steps here makes `/capture/link` easier to reason about without changing its
external contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(slots=True)
class LinkFetchResult:
    url: str
    title: str = ""
    description: str = ""
    text: str = ""
    content_type: str = ""
    links: list[dict[str, Any]] = field(default_factory=list)
    status_code: int | None = None
    final_url: str = ""
    fetch_error: str = ""

    @property
    def ok(self) -> bool:
        return not self.fetch_error and bool(self.text or self.title or self.description)


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}


def _html_metadata(html: str) -> tuple[str, str, list[dict[str, Any]]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    desc = ""
    for attrs in (
        {"name": "description"},
        {"property": "og:description"},
        {"name": "Description"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            desc = str(tag.get("content") or "").strip()
            break
    links: list[dict[str, Any]] = []
    for link_tag in soup.find_all("a", href=True)[:40]:
        links.append(
            {
                "url": str(link_tag.get("href") or ""),
                "text": link_tag.get_text(" ", strip=True)[:160],
            }
        )
    return title, desc, links


def _extract_with_trafilatura(html: str, *, url: str) -> str:
    try:
        import trafilatura

        extracted = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            output_format="txt",
            favor_recall=True,
        )
        return (extracted or "").strip()
    except Exception:
        return ""


def _extract_with_bs4(html: str, *, max_length: int) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "canvas", "iframe"]):
        tag.decompose()
    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )
    text = main.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:max_length].strip()


def _extract_text(html: str, *, url: str, max_length: int = 30000) -> str:
    text = _extract_with_trafilatura(html, url=url)
    if len(text) < 120:
        text = _extract_with_bs4(html, max_length=max_length)
    return text[:max_length].strip()


async def fetch_link_content(url: str, *, timeout: int = 15) -> LinkFetchResult | None:
    """Fetch a URL and return clean text suitable for LLM enrichment."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            verify=False,
            headers=_BROWSER_HEADERS,
        ) as client:
            response = await client.get(url)
    except Exception as exc:  # noqa: BLE001
        return LinkFetchResult(url=url, fetch_error=f"请求失败：{exc}")

    content_type = response.headers.get("content-type", "")
    final_url = str(response.url)
    if response.status_code >= 400:
        return LinkFetchResult(
            url=url,
            content_type=content_type,
            status_code=response.status_code,
            final_url=final_url,
            fetch_error=f"远端返回 HTTP {response.status_code}",
        )

    raw_page = response.text
    if "html" in content_type.lower() or raw_page.lstrip().lower().startswith("<!doctype"):
        title, description, links = _html_metadata(raw_page)
        text = _extract_text(raw_page, url=final_url)
    else:
        title = ""
        description = ""
        links = []
        text = raw_page.strip()[:30000]

    if not (text or title or description):
        return LinkFetchResult(
            url=url,
            content_type=content_type,
            status_code=response.status_code,
            final_url=final_url,
            fetch_error="没有提取到可保存的正文",
        )

    return LinkFetchResult(
        url=url,
        title=title,
        description=description,
        text=text,
        content_type=content_type,
        links=links,
        status_code=response.status_code,
        final_url=final_url,
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
        "status_code": fetched.status_code,
        "final_url": fetched.final_url or fetched.url,
        "fetch_error": fetched.fetch_error,
        "text_excerpt": fetched.text[:1000],
    }
