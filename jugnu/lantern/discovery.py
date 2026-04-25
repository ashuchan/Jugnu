from __future__ import annotations

from jugnu.contracts import FetchResult
from jugnu.lantern.api_heuristics import looks_like_api_endpoint
from jugnu.lantern.link_extractor import extract_api_urls, extract_links
from jugnu.lantern.link_ranker import rank_links


class Lantern:
    """Discovery layer — given a FetchResult, surfaces ranked links and API endpoints."""

    def __init__(
        self,
        keywords: list[str] | None = None,
        api_patterns: list[str] | None = None,
        negative_keywords: list[str] | None = None,
        confidence_threshold: float = 0.4,
    ) -> None:
        self._keywords = keywords or []
        self._api_patterns = api_patterns or []
        self._negative_keywords = negative_keywords or []
        self._threshold = confidence_threshold

    def discover(
        self,
        fetch_result: FetchResult,
    ) -> DiscoveryResult:
        html = fetch_result.html
        base = fetch_result.url

        links = extract_links(base, html)
        api_urls = extract_api_urls(html, base)

        ranked = rank_links(
            links + api_urls,
            self._keywords,
            self._negative_keywords,
            threshold=self._threshold,
        )

        confirmed_apis = [
            url
            for url in api_urls
            if looks_like_api_endpoint(url, fetch_result.content_type)
            or any(pat in url for pat in self._api_patterns)
        ]

        return DiscoveryResult(
            ranked_links=ranked,
            api_endpoints=confirmed_apis,
            all_links=links,
        )


class DiscoveryResult:
    def __init__(
        self,
        ranked_links: list[tuple[str, float]],
        api_endpoints: list[str],
        all_links: list[str],
    ) -> None:
        self.ranked_links = ranked_links
        self.api_endpoints = api_endpoints
        self.all_links = all_links

    def top_links(self, n: int = 10) -> list[str]:
        return [url for url, _ in self.ranked_links[:n]]

    def above_threshold(self, threshold: float) -> list[tuple[str, float]]:
        return [(url, score) for url, score in self.ranked_links if score >= threshold]
