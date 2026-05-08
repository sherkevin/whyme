"""Web Crawler Module - Stage 4 Implementation.

Extracts content and metadata from URLs.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WebCrawler:
    """
    网页爬虫 - 提取网页内容和元数据

    使用 aiohttp 和 BeautifulSoup (Stage 4 简化版本)
    """

    def __init__(self, timeout: int = 10, user_agent: str = None):
        """
        初始化爬虫

        Args:
            timeout: 请求超时时间(秒)
            user_agent: User-Agent字符串
        """
        self.timeout = timeout
        self.user_agent = user_agent or (
            "Mozilla/5.0 (compatible; AgentOS/1.0; +https://agentos.ai)"
        )

    async def fetch_page(
        self,
        url: str,
        session: Any = None
    ) -> dict[str, Any] | None:
        """
        抓取网页内容

        Args:
            url: 目标URL
            session: aiohttp Session (可选)

        Returns:
            网页数据字典，失败返回None
        """
        import aiohttp

        try:
            if session is None:
                # 创建临时session
                async with aiohttp.ClientSession() as session:
                    return await self._fetch_with_session(session, url)
            else:
                return await self._fetch_with_session(session, url)

        except Exception as e:
            logger.error(f"Error fetching page {url}: {e}")
            return None

    async def _fetch_with_session(
        self,
        session: Any,  # aiohttp.ClientSession
        url: str
    ) -> dict[str, Any] | None:
        """
        使用已有session抓取页面

        Args:
            session: aiohttp Session
            url: 目标URL

        Returns:
            网页数据字典
        """
        headers = {
            'User-Agent': self.user_agent
        }

        async with session.get(url, headers=headers, timeout=self.timeout) as response:
            if response.status != 200:
                logger.warning(f"HTTP {response.status} for {url}")
                return None

            # 读取内容
            content_type = response.headers.get('Content-Type', '')
            content = await response.text()

            # 解析HTML
            soup = None
            title = None
            description = None
            links = []

            if 'html' in content_type.lower():
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(content, 'html.parser')

                # 提取标题
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.string

                # 提取描述
                desc_tag = soup.find('meta', attrs={'name': 'description'})
                if desc_tag:
                    description = desc_tag.get('content', '')

                # 提取所有链接
                for link_tag in soup.find_all('a', href=True):
                    link_url = link_tag['href']
                    link_text = link_tag.get_text()
                    links.append({
                        'url': link_url,
                        'text': link_text.strip()
                    })

            return {
                'url': url,
                'title': title,
                'description': description,
                'content': content[:5000],  # 限制内容长度
                'links': links[:20],  # 限制链接数量
                'content_type': content_type
            }

    def extract_metadata(
        self,
        url: str,
        html_content: str
    ) -> dict[str, Any]:
        """
        从HTML内容中提取元数据

        Args:
            url: 页面URL
            html_content: HTML内容

        Returns:
            元数据字典
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, 'html.parser')

        # 提取标题
        title_tag = soup.find('title')
        title = title_tag.string if title_tag else None

        # 提取各种meta标签
        metadata = {}

        # Description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            metadata['description'] = desc_tag.get('content', '')

        # Keywords
        keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
        if keywords_tag:
            metadata['keywords'] = keywords_tag.get('content', '').split(',')

        # OG Tags (Open Graph)
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        if og_title:
            metadata['og_title'] = og_title.get('content', '')

        og_description = soup.find('meta', attrs={'property': 'og:description'})
        if og_description:
            metadata['og_description'] = og_description.get('content', '')

        og_image = soup.find('meta', attrs={'property': 'og:image'})
        if og_image:
            metadata['og_image'] = og_image.get('content', '')

        # 提取所有链接
        links = []
        for link_tag in soup.find_all('a', href=True):
            link_url = link_tag['href']
            link_text = link_tag.get_text().strip()
            links.append({
                'url': link_url,
                'text': link_text
            })

        return {
            'url': url,
            'title': title,
            'metadata': metadata,
            'links': links[:20]
        }

    def extract_text_content(
        self,
        html_content: str,
        max_length: int = 5000
    ) -> str:
        """
        从HTML中提取纯文本内容

        Args:
            html_content: HTML内容
            max_length: 最大长度限制

        Returns:
            纯文本内容
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, 'html.parser')

        # 移除script和style标签
        for script in soup(['script', 'style']):
            script.decompose()

        # 获取文本
        text = soup.get_text(separator=' ', strip=True)

        # 清理多余的空格
        text = re.sub(r'\s+', ' ', text)

        # 限制长度
        if len(text) > max_length:
            text = text[:max_length] + '...'

        return text.strip()

    async def download_image(
        self,
        image_url: str,
        save_path: str,
        session: Any = None
    ) -> bool:
        """
        下载图片

        Args:
            image_url: 图片URL
            save_path: 保存路径
            session: aiohttp Session (可选)

        Returns:
            是否成功
        """
        import aiohttp

        try:
            if session is None:
                async with aiohttp.ClientSession() as session:
                    return await self._download_image_with_session(session, image_url, save_path)
            else:
                return await self._download_image_with_session(session, image_url, save_path)

        except Exception as e:
            logger.error(f"Error downloading image {image_url}: {e}")
            return False

    async def _download_image_with_session(
        self,
        session: Any,  # aiohttp.ClientSession
        image_url: str,
        save_path: str
    ) -> bool:
        """使用已有session下载图片"""

        headers = {'User-Agent': self.user_agent}

        async with session.get(image_url, headers=headers, timeout=self.timeout) as response:
            if response.status != 200:
                logger.warning(f"HTTP {response.status} for image {image_url}")
                return False

            content = await response.read()

            # 保存文件
            import os
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            with open(save_path, 'wb') as f:
                f.write(content)

            logger.info(f"Downloaded image to {save_path}")
            return True

    def extract_urls_from_text(self, text: str) -> list[str]:
        """
        从文本中提取所有URL (便捷方法)

        Args:
            text: 输入文本

        Returns:
            URL列表
        """
        return LinkExtractor().extract_urls(text)


# =============================================================================
# 便捷函数
# ============================================================================

async def crawl_url(
    url: str,
    crawler: WebCrawler | None = None
) -> dict[str, Any] | None:
    """
    抓取单个URL (便捷函数)

    Args:
        url: 目标URL
        crawler: WebCrawler实例 (可选)

    Returns:
        爬取结果
    """
    if crawler is None:
        crawler = WebCrawler()

    return await crawler.fetch_page(url)


class LinkExtractor:
    """链接提取器 (在wechat.py中也定义，这里提供便捷访问)"""

    URL_PATTERN = r'https?://\S+'

    def extract_urls(self, text: str) -> list[str]:
        """从文本中提取所有URL"""
        import re

        if not text:
            return []

        urls = re.findall(self.URL_PATTERN, text, re.IGNORECASE)

        # 清理URL - 移除末尾的标点符号
        cleaned_urls = []
        for url in urls:
            # 移除末尾的标点符号
            while url and url[-1] in '.,，。！!??:;；：':
                url = url[:-1]
            if url:
                cleaned_urls.append(url)

        return list(set(cleaned_urls))

    def extract_first_url(self, text: str) -> str | None:
        """提取第一个URL"""
        urls = self.extract_urls(text)
        return urls[0] if urls else None
