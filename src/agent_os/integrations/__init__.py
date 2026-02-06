"""Integrations Module - WeChat, Webhook, and Crawler.

Stage 4 Implementation:
- WeChat Webhook Receiver
- Web Crawler (aiohttp + BeautifulSoup)
- Link Extractor
- FastAPI Router for integrations
"""

from agent_os.integrations.wechat import (
    WeChatWebhookReceiver,
    LinkExtractor,
    process_wechat_message
)

from agent_os.integrations.crawler import (
    WebCrawler,
    crawl_url
)

from agent_os.integrations import router

__all__ = [
    # WeChat
    "WeChatWebhookReceiver",
    "LinkExtractor",
    "process_wechat_message",
    # Crawler
    "WebCrawler",
    "crawl_url",
    # Router
    "router"
]
