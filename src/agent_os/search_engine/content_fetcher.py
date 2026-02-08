"""Content Fetcher - Fetches content from external sources.

This module provides functionality for:
- Fetching content from URLs (HTML, Markdown, plain text)
- Extracting text from PDF files
- Content cleaning and normalization
"""

import logging
import re
from typing import Optional
from pathlib import Path

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logging.warning("aiohttp not available, URL fetching will be limited")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logging.warning("beautifulsoup4 not available, HTML parsing will be limited")

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logging.warning("PyPDF2 not available, PDF extraction will be limited")

logger = logging.getLogger(__name__)


class ContentFetcher:
    """Content fetcher for URLs and PDFs."""

    def __init__(self, timeout: int = 30):
        """Initialize content fetcher.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

    async def fetch_url(
        self,
        url: str,
        timeout: Optional[int] = None
    ) -> str:
        """Fetch content from URL.

        Args:
            url: URL to fetch
            timeout: Override default timeout

        Returns:
            Extracted text content

        Raises:
            ValueError: If URL is invalid
            RuntimeError: If fetching fails
        """
        if not AIOHTTP_AVAILABLE:
            raise RuntimeError("aiohttp is required for URL fetching. Install: pip install aiohttp")

        timeout = timeout or self.timeout

        # Validate URL
        if not self._is_valid_url(url):
            raise ValueError(f"Invalid URL: {url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    response.raise_for_status()

                    # Detect content type
                    content_type = response.headers.get('Content-Type', '')

                    if 'html' in content_type:
                        html_content = await response.text()
                        return self._extract_html_text(html_content, url)
                    elif 'markdown' in content_type or url.endswith('.md'):
                        return await response.text()
                    else:
                        # Assume plain text
                        return await response.text()

        except aiohttp.ClientError as e:
            logger.error(f"Failed to fetch URL {url}: {e}")
            raise RuntimeError(f"Failed to fetch URL: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching URL {url}: {e}")
            raise RuntimeError(f"Failed to fetch URL: {e}")

    async def fetch_pdf(self, file_path: str) -> str:
        """Extract text from PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted text content

        Raises:
            FileNotFoundError: If file doesn't exist
            RuntimeError: If extraction fails
        """
        if not PYPDF2_AVAILABLE:
            raise RuntimeError("PyPDF2 is required for PDF extraction. Install: pip install PyPDF2")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        try:
            import PyPDF2

            text_parts = []
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)

                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    if text.strip():
                        text_parts.append(text)

            return '\n\n'.join(text_parts)

        except Exception as e:
            logger.error(f"Failed to extract PDF from {file_path}: {e}")
            raise RuntimeError(f"Failed to extract PDF: {e}")

    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format.

        Args:
            url: URL to validate

        Returns:
            True if valid
        """
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None

    def _extract_html_text(self, html: str, url: str) -> str:
        """Extract clean text from HTML.

        Args:
            html: HTML content
            url: Source URL (for metadata)

        Returns:
            Extracted and cleaned text
        """
        if not BS4_AVAILABLE:
            # Fallback: remove HTML tags using regex
            text = re.sub(r'<script[^>]*?>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*?>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Remove script and style elements
            for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text

        except Exception as e:
            logger.error(f"Failed to parse HTML from {url}: {e}")
            # Fallback to regex
            text = re.sub(r'<[^>]+>', '', html)
            return re.sub(r'\s+', ' ', text).strip()

    async def fetch_markdown(self, file_path: str) -> str:
        """Fetch content from Markdown file.

        Args:
            file_path: Path to markdown file

        Returns:
            File content

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {file_path}")

        try:
            return path.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read markdown file {file_path}: {e}")
            raise RuntimeError(f"Failed to read markdown file: {e}")


class ContentFetchResult:
    """Result of content fetch operation."""

    def __init__(
        self,
        success: bool,
        content: str,
        source: str,
        metadata: dict = None,
        error: str = None
    ):
        self.success = success
        self.content = content
        self.source = source
        self.metadata = metadata or {}
        self.error = error

    def __repr__(self):
        if self.success:
            return f"<ContentFetchResult(success=True, source={self.source}, length={len(self.content)})"
        else:
            return f"<ContentFetchResult(success=False, error={self.error})>"
