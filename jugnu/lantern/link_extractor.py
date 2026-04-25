from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


def extract_links(base_url: str, html: str) -> list[str]:
    """Extract all href links from HTML, resolved to absolute URLs."""
    links: list[str] = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            abs_url = urljoin(base_url, href)
            parsed = urlparse(abs_url)
            if parsed.scheme in ("http", "https"):
                links.append(abs_url)
    except Exception:  # noqa: BLE001
        pass
    return links


def extract_api_urls(html: str, base_url: str) -> list[str]:
    """Extract likely API/XHR endpoint URLs from script tags and data attributes."""
    import re  # noqa: PLC0415

    endpoints: list[str] = []
    # JSON-like strings containing /api/, /v1/, /v2/, etc.
    pattern = re.compile(r'["\']([/][\w\-./]+(?:api|v\d|json|data|feed)[\w\-./]*)["\']')
    try:
        for match in pattern.finditer(html):
            path = match.group(1)
            abs_url = urljoin(base_url, path)
            if abs_url not in endpoints:
                endpoints.append(abs_url)
    except Exception:  # noqa: BLE001
        pass
    return endpoints
