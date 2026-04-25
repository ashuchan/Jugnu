"""Helper for assembling Prompt-1 inputs from a fetch result + SkillMemory.

DiscoveryLLM owns the prompt template; this module owns the *candidate
preparation* — extracting and de-noising link/API candidates so the LLM has
clean, ranked-input data to reason over.
"""
from __future__ import annotations

from urllib.parse import urlparse

from jugnu.contracts import FetchResult
from jugnu.lantern.api_heuristics import looks_like_data_api
from jugnu.lantern.link_extractor import extract_api_urls, extract_links
from jugnu.spark.skill_memory import SkillMemory


def build_discovery_candidates(
    fetch_result: FetchResult,
    output_fields: list[str],
    memory: SkillMemory | None = None,
    max_links: int = 50,
    max_apis: int = 25,
) -> tuple[list[dict], list[dict]]:
    """Return (api_candidates, link_candidates) ready for Prompt-1.

    Each candidate is `{url|href, score, reason}`. Score is a deterministic
    pre-rank that the LLM can override; pre-ranking lets us truncate to N
    candidates without losing the strongest signals.
    """
    base = fetch_result.url
    html = fetch_result.html
    learned_patterns = memory.high_confidence_api_patterns if memory else []
    learned_keywords = memory.high_confidence_link_keywords if memory else []
    noise = memory.known_noise_patterns if memory else []

    raw_links = extract_links(base, html)
    raw_apis = extract_api_urls(html, base)

    api_candidates: list[dict] = []
    seen_apis: set[str] = set()
    for url in raw_apis:
        if url in seen_apis:
            continue
        seen_apis.add(url)
        if not looks_like_data_api(url, learned_patterns=learned_patterns, noise_patterns=noise):
            continue
        score, reason = _score_api(url, learned_patterns)
        api_candidates.append({"url": url, "score": score, "reason": reason})

    link_candidates: list[dict] = []
    seen_links: set[str] = set()
    base_host = urlparse(base).netloc
    for url in raw_links:
        if url in seen_links:
            continue
        seen_links.add(url)
        if any(n.lower() in url.lower() for n in noise if n):
            continue
        if urlparse(url).netloc != base_host:
            continue
        score, reason = _score_link(url, learned_keywords, output_fields)
        link_candidates.append({"href": url, "score": score, "reason": reason})

    api_candidates.sort(key=lambda c: c["score"], reverse=True)
    link_candidates.sort(key=lambda c: c["score"], reverse=True)
    return api_candidates[:max_apis], link_candidates[:max_links]


def _score_api(url: str, learned_patterns: list[str]) -> tuple[float, str]:
    lowered = url.lower()
    for pat in learned_patterns:
        if pat and pat.lower() in lowered:
            return 0.95, f"matches learned api pattern '{pat}'"
    return 0.5, "generic api shape"


def _score_link(url: str, keywords: list[str], output_fields: list[str]) -> tuple[float, str]:
    lowered = url.lower()
    keyword_hits = [kw for kw in keywords if kw and kw.lower() in lowered]
    field_hits = [f for f in output_fields if f and f.lower() in lowered]
    score = 0.0
    reason_bits: list[str] = []
    if keyword_hits:
        score += 0.6
        reason_bits.append(f"learned keyword match: {keyword_hits[0]}")
    if field_hits:
        score += 0.3
        reason_bits.append(f"path mentions schema field: {field_hits[0]}")
    if not reason_bits:
        return 0.1, "no learned signal"
    return min(score, 1.0), "; ".join(reason_bits)
