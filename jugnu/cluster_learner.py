"""Profile clustering — group similar profiles and bootstrap new ones from peers.

Spec (Phase 8): grouped by domain + platform + JSON-path signature; new profile
copies api_hints/dom_hints from a matching cluster and starts at WARM maturity.
"""
from __future__ import annotations

from urllib.parse import urlparse

from jugnu.profile import (
    ApiHints,
    DomHints,
    NavigationConfig,
    ProfileMaturity,
    ScrapeProfile,
)


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc or url
    except Exception:  # noqa: BLE001
        return url


def _api_signature(profile: ScrapeProfile) -> str:
    """Stable signature derived from confirmed API patterns (sorted)."""
    patterns = sorted(profile.api_hints.confirmed_patterns)
    return "|".join(patterns)


def cluster_by_domain(profiles: list[ScrapeProfile]) -> dict[str, list[ScrapeProfile]]:
    """Group profiles by root domain. Retained for backwards compatibility."""
    clusters: dict[str, list[ScrapeProfile]] = {}
    for p in profiles:
        clusters.setdefault(_domain(p.url_pattern), []).append(p)
    return clusters


def find_similar_profiles(
    target: ScrapeProfile,
    candidates: list[ScrapeProfile],
    min_platform_match: bool = True,
) -> list[ScrapeProfile]:
    """Return profiles sharing the target's platform. Retained for backwards compatibility."""
    if not target.platform:
        return []
    return [
        p
        for p in candidates
        if p.platform == target.platform and p.url_pattern != target.url_pattern
    ]


def find_cluster(
    target: ScrapeProfile,
    candidates: list[ScrapeProfile],
) -> list[ScrapeProfile]:
    """Find candidates sharing domain + platform + API signature with target.

    Per Phase 8 spec: cluster key is (domain, platform_guess, json_path_signature).
    """
    target_domain = _domain(target.url_pattern)
    target_sig = _api_signature(target)
    cluster: list[ScrapeProfile] = []
    for p in candidates:
        if p.url_pattern == target.url_pattern:
            continue
        if _domain(p.url_pattern) != target_domain:
            continue
        if target.platform and p.platform and target.platform != p.platform:
            continue
        if target_sig and _api_signature(p) and _api_signature(p) != target_sig:
            continue
        cluster.append(p)
    return cluster


def bootstrap_from_cluster(
    target: ScrapeProfile,
    cluster: list[ScrapeProfile],
) -> ScrapeProfile:
    """Copy api_hints + dom_hints + navigation_config from cluster into target.

    Sets maturity to WARM so the new profile skips the cold-start LLM cascade.
    Picks the most-mature peer as the donor; falls back to the first peer.
    No-op if the cluster is empty.
    """
    if not cluster:
        return target

    maturity_rank = {
        ProfileMaturity.STABLE: 3,
        ProfileMaturity.WARM: 2,
        ProfileMaturity.LEARNING: 1,
        ProfileMaturity.COLD: 0,
    }
    donor = max(cluster, key=lambda p: maturity_rank.get(p.maturity, 0))

    # Merge endpoints/patterns deduped, preserve donor's other fields
    t_api = target.api_hints
    d_api = donor.api_hints
    merged_endpoints = sorted(set(t_api.confirmed_endpoints) | set(d_api.confirmed_endpoints))
    merged_patterns = sorted(set(t_api.confirmed_patterns) | set(d_api.confirmed_patterns))
    target.api_hints = ApiHints(
        confirmed_endpoints=merged_endpoints,
        confirmed_patterns=merged_patterns,
        auth_required=d_api.auth_required or t_api.auth_required,
        pagination_style=t_api.pagination_style or d_api.pagination_style,
        response_format=t_api.response_format or d_api.response_format,
    )

    t_dom = target.dom_hints
    d_dom = donor.dom_hints
    merged_selectors = {**d_dom.confirmed_selectors, **t_dom.confirmed_selectors}
    merged_lists = sorted(set(t_dom.list_container_selectors) | set(d_dom.list_container_selectors))
    merged_pagination = sorted(set(t_dom.pagination_selectors) | set(d_dom.pagination_selectors))
    merged_noise = sorted(set(t_dom.noise_selectors) | set(d_dom.noise_selectors))
    target.dom_hints = DomHints(
        confirmed_selectors=merged_selectors,
        list_container_selectors=merged_lists,
        pagination_selectors=merged_pagination,
        noise_selectors=merged_noise,
    )

    if not target.navigation_config.wait_for_selector and donor.navigation_config.wait_for_selector:
        target.navigation_config = NavigationConfig(
            requires_interaction=donor.navigation_config.requires_interaction,
            scroll_for_content=donor.navigation_config.scroll_for_content,
            wait_for_selector=donor.navigation_config.wait_for_selector,
            wait_ms=donor.navigation_config.wait_ms,
            external_sources=list(donor.navigation_config.external_sources),
            pre_crawl_steps=list(donor.navigation_config.pre_crawl_steps),
        )

    if not target.platform and donor.platform:
        target.platform = donor.platform

    target.maturity = ProfileMaturity.WARM
    return target
