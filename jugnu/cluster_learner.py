from __future__ import annotations

from urllib.parse import urlparse

from jugnu.profile import ScrapeProfile


def cluster_by_domain(profiles: list[ScrapeProfile]) -> dict[str, list[ScrapeProfile]]:
    """Group profiles by root domain."""
    clusters: dict[str, list[ScrapeProfile]] = {}
    for p in profiles:
        try:
            domain = urlparse(p.url_pattern).netloc or p.url_pattern
        except Exception:  # noqa: BLE001
            domain = p.url_pattern
        clusters.setdefault(domain, []).append(p)
    return clusters


def find_similar_profiles(
    target: ScrapeProfile,
    candidates: list[ScrapeProfile],
    min_platform_match: bool = True,
) -> list[ScrapeProfile]:
    """Return profiles that share the same platform as target."""
    if not target.platform:
        return []
    return [
        p
        for p in candidates
        if p.platform == target.platform and p.url_pattern != target.url_pattern
    ]
