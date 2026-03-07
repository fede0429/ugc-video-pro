"""
services/url_extractor.py
=========================
Extract product information from URLs for URL-reference-to-video mode.

Supports e-commerce product pages (Amazon, Taobao, Shopify, etc.)
and general web pages via BeautifulSoup + JSON-LD structured data extraction.
"""

import re
from typing import Optional

import aiohttp
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_CONTENT_LENGTH = 8000
REQUEST_TIMEOUT = 30

CONTENT_SELECTORS = [
    "#productTitle", "#product-title", ".product-title", ".product-name",
    "h1.product_title", "#title", "h1",
    "#productDescription", "#feature-bullets", ".product-description",
    ".product_description", "[data-testid='product-description']",
    "#description", ".description", "article", "main",
]


class URLExtractor:
    """Extract product information from a URL for use in video script generation."""

    def __init__(self, config: dict):
        self.config = config
        url_config = config.get("url_extraction", {})
        self.timeout = url_config.get("timeout", REQUEST_TIMEOUT)
        self.max_length = url_config.get("max_length", MAX_CONTENT_LENGTH)
        self.user_agent = url_config.get(
            "user_agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    async def extract(self, url: str) -> Optional[str]:
        """Extract product information from a URL."""
        logger.info(f"Extracting content from: {url}")

        try:
            html = await self._fetch_html(url)
        except Exception as e:
            logger.warning(f"Failed to fetch URL: {e}")
            return None

        if not html:
            return None

        content = self._extract_structured(html, url)

        if not content or len(content) < 100:
            content = self._extract_text(html)

        if content:
            content = content[:self.max_length]
            logger.info(f"Extracted {len(content)} chars from URL")

        return content

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                allow_redirects=True, ssl=False,
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"URL returned status {resp.status}: {url}")
                    return None

                content_type = resp.headers.get("content-type", "")
                if "text" not in content_type and "html" not in content_type:
                    logger.warning(f"Non-HTML content type: {content_type}")
                    return None

                content = await resp.read()
                try:
                    return content.decode("utf-8")
                except UnicodeDecodeError:
                    return content.decode("latin-1", errors="replace")

    def _extract_structured(self, html: str, url: str) -> Optional[str]:
        """Extract structured product information using BeautifulSoup."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.warning("BeautifulSoup not available, using text fallback")
            return None

        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all(["script", "style", "nav", "footer", "header",
                                   "aside", "iframe", "noscript", "meta"]):
            tag.decompose()

        extracted_parts = []

        title = soup.find("h1")
        if title:
            title_text = title.get_text(strip=True)
            if title_text:
                extracted_parts.append(f"Product: {title_text}")

        seen_text = set()
        for selector in CONTENT_SELECTORS:
            try:
                elements = soup.select(selector)
                for elem in elements[:3]:
                    text = elem.get_text(separator=" ", strip=True)
                    if len(text) < 20 or text in seen_text:
                        continue
                    seen_text.add(text)
                    extracted_parts.append(text)
            except Exception:
                continue

        ld_content = self._extract_json_ld(soup)
        if ld_content:
            extracted_parts.append(ld_content)

        if extracted_parts:
            return "\n\n".join(extracted_parts[:10])
        return None

    def _extract_json_ld(self, soup) -> Optional[str]:
        """Extract product information from JSON-LD structured data."""
        try:
            import json
            ld_scripts = soup.find_all("script", type="application/ld+json")
            for script in ld_scripts:
                try:
                    data = json.loads(script.string or "")
                    if isinstance(data, list):
                        data = data[0] if data else {}

                    schema_type = data.get("@type", "")
                    if "Product" in str(schema_type):
                        parts = []
                        if data.get("name"):
                            parts.append(f"Product Name: {data['name']}")
                        if data.get("description"):
                            parts.append(f"Description: {data['description'][:500]}")
                        if data.get("brand"):
                            brand = data["brand"]
                            if isinstance(brand, dict):
                                brand = brand.get("name", "")
                            if brand:
                                parts.append(f"Brand: {brand}")
                        if parts:
                            return "\n".join(parts)
                except (json.JSONDecodeError, Exception):
                    continue
        except Exception:
            pass
        return None

    def _extract_text(self, html: str) -> Optional[str]:
        """Fallback: extract plain text from HTML."""
        try:
            import html2text
            converter = html2text.HTML2Text()
            converter.ignore_links = True
            converter.ignore_images = True
            converter.ignore_emphasis = False
            converter.body_width = 0
            text = converter.handle(html)

            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r"[ \t]+", " ", text)
            text = text.strip()

            lines = [l for l in text.split("\n") if len(l.strip()) > 10]
            return "\n".join(lines[:100])

        except ImportError:
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:self.max_length]
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return None
