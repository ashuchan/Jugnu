from __future__ import annotations

from jugnu.cluster_learner import (
    bootstrap_from_cluster,
    cluster_by_domain,
    find_cluster,
    find_similar_profiles,
)
from jugnu.profile import ApiHints, DomHints, ProfileMaturity, ScrapeProfile


def _profile(url: str, *, platform: str | None = None, patterns: list[str] | None = None,
             maturity: ProfileMaturity = ProfileMaturity.COLD,
             selectors: dict[str, str] | None = None) -> ScrapeProfile:
    return ScrapeProfile(
        url_pattern=url,
        platform=platform,
        maturity=maturity,
        api_hints=ApiHints(confirmed_patterns=patterns or []),
        dom_hints=DomHints(confirmed_selectors=selectors or {}),
    )


def test_cluster_by_domain_groups_by_netloc():
    profiles = [
        _profile("https://a.com/x"),
        _profile("https://a.com/y"),
        _profile("https://b.com/z"),
    ]
    grouped = cluster_by_domain(profiles)
    assert "a.com" in grouped
    assert len(grouped["a.com"]) == 2
    assert len(grouped["b.com"]) == 1


def test_find_similar_profiles_matches_platform():
    target = _profile("https://a.com/x", platform="rentcafe")
    others = [
        _profile("https://b.com/y", platform="rentcafe"),
        _profile("https://c.com/z", platform="entrata"),
    ]
    matches = find_similar_profiles(target, others)
    assert len(matches) == 1
    assert matches[0].platform == "rentcafe"


def test_find_cluster_filters_by_domain_platform_and_signature():
    target = _profile(
        "https://a.com/x",
        platform="rentcafe",
        patterns=["/api/getFloorplans"],
    )
    others = [
        # same domain + platform + signature → cluster member
        _profile("https://a.com/y", platform="rentcafe", patterns=["/api/getFloorplans"]),
        # different domain → excluded
        _profile("https://b.com/x", platform="rentcafe", patterns=["/api/getFloorplans"]),
        # same domain, different platform → excluded
        _profile("https://a.com/z", platform="entrata", patterns=["/api/getFloorplans"]),
    ]
    cluster = find_cluster(target, others)
    assert len(cluster) == 1
    assert cluster[0].url_pattern == "https://a.com/y"


def test_bootstrap_from_cluster_promotes_to_warm_and_copies_hints():
    target = _profile("https://a.com/new")
    donor = _profile(
        "https://a.com/donor",
        platform="rentcafe",
        patterns=["/api/getFloorplans"],
        maturity=ProfileMaturity.STABLE,
        selectors={"price": ".rent-price"},
    )
    bootstrapped = bootstrap_from_cluster(target, [donor])
    assert bootstrapped.maturity == ProfileMaturity.WARM
    assert "/api/getFloorplans" in bootstrapped.api_hints.confirmed_patterns
    assert bootstrapped.dom_hints.confirmed_selectors.get("price") == ".rent-price"
    assert bootstrapped.platform == "rentcafe"


def test_bootstrap_from_empty_cluster_is_noop():
    target = _profile("https://a.com/x")
    out = bootstrap_from_cluster(target, [])
    assert out.maturity == ProfileMaturity.COLD


def test_bootstrap_picks_most_mature_donor():
    target = _profile("https://a.com/new")
    cold = _profile("https://a.com/cold", platform="rentcafe", patterns=["/cold"], maturity=ProfileMaturity.COLD)
    stable = _profile("https://a.com/stable", platform="rentcafe", patterns=["/stable"], maturity=ProfileMaturity.STABLE)
    out = bootstrap_from_cluster(target, [cold, stable])
    # Stable donor's pattern is included
    assert "/stable" in out.api_hints.confirmed_patterns
