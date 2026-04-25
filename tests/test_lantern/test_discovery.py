from __future__ import annotations

import pytest

from jugnu.contracts import FetchResult
from jugnu.lantern.api_heuristics import looks_like_api_endpoint, score_api_pattern
from jugnu.lantern.discovery import DiscoveryResult, Lantern
from jugnu.lantern.link_extractor import extract_api_urls, extract_links
from jugnu.lantern.link_ranker import rank_links


SAMPLE_HTML = """
<html><body>
  <a href="/articles/news-today">News Today</a>
  <a href="/articles/sports-update">Sports Update</a>
  <a href="/about">About Us</a>
  <a href="https://external.com/blog">External Blog</a>
  <a href="javascript:void(0)">JS Link</a>
  <a href="#anchor">Anchor</a>
</body></html>
"""


def test_extract_links_basic():
    links = extract_links("https://example.com", SAMPLE_HTML)
    assert any("/articles/news-today" in l for l in links)
    assert all(l.startswith("http") for l in links)


def test_extract_links_ignores_js_and_anchors():
    links = extract_links("https://example.com", SAMPLE_HTML)
    assert not any("javascript:" in l for l in links)
    assert not any(l == "#anchor" for l in links)


def test_extract_links_absolute():
    links = extract_links("https://example.com", SAMPLE_HTML)
    assert "https://external.com/blog" in links


def test_rank_links_with_keywords():
    links = [
        "https://example.com/articles/news",
        "https://example.com/about",
        "https://example.com/articles/sport",
    ]
    ranked = rank_links(links, keywords=["articles"])
    top = [url for url, _ in ranked[:2]]
    assert all("articles" in u for u in top)


def test_rank_links_negative_keywords():
    links = [
        "https://example.com/articles/news",
        "https://example.com/admin/panel",
    ]
    ranked = rank_links(links, keywords=["articles"], negative_keywords=["admin"])
    urls = [url for url, _ in ranked]
    assert not any("admin" in u for u in urls)


def test_api_heuristic_json_url():
    assert looks_like_api_endpoint("https://api.example.com/v2/listings.json") is True


def test_api_heuristic_content_type():
    assert looks_like_api_endpoint("https://example.com/data", "application/json") is True


def test_api_heuristic_negative():
    assert looks_like_api_endpoint("https://example.com/about") is False


def test_score_api_pattern():
    urls = [
        "https://example.com/api/v1/items",
        "https://example.com/api/v1/categories",
        "https://example.com/about",
    ]
    score = score_api_pattern("/api/", urls)
    assert score == pytest.approx(2 / 3, rel=0.01)


def test_lantern_discover():
    fetch = FetchResult(
        url="https://example.com",
        status_code=200,
        html=SAMPLE_HTML,
    )
    lantern = Lantern(keywords=["articles"], confidence_threshold=0.0)
    result = lantern.discover(fetch)
    assert isinstance(result, DiscoveryResult)
    assert len(result.all_links) > 0
    top = result.top_links(5)
    assert all(isinstance(u, str) for u in top)
