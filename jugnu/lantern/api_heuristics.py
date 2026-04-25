from __future__ import annotations

import re
from urllib.parse import urlparse

_API_PATH_PATTERNS = [
    re.compile(r"/api/"),
    re.compile(r"/v\d+/"),
    re.compile(r"\.json(\?|$)"),
    re.compile(r"/graphql"),
    re.compile(r"/feed"),
    re.compile(r"/rss"),
    re.compile(r"/sitemap"),
    re.compile(r"/data/"),
    re.compile(r"/search\?"),
    re.compile(r"/listings\?"),
]

_API_CONTENT_TYPES = {
    "application/json",
    "application/ld+json",
    "application/xml",
    "text/xml",
    "application/atom+xml",
    "application/rss+xml",
}


def looks_like_api_endpoint(url: str, content_type: str = "") -> bool:
    ct = content_type.lower().split(";")[0].strip()
    if ct in _API_CONTENT_TYPES:
        return True
    return any(p.search(url) for p in _API_PATH_PATTERNS)


def score_api_pattern(pattern: str, observed_urls: list[str]) -> float:
    """Return 0.0-1.0 confidence that a pattern matches observed API URLs."""
    if not observed_urls:
        return 0.0
    hits = sum(1 for u in observed_urls if pattern in u)
    return hits / len(observed_urls)
