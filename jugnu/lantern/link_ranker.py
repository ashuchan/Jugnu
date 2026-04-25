from __future__ import annotations

import re
from urllib.parse import urlparse


def rank_links(
    links: list[str],
    keywords: list[str],
    negative_keywords: list[str] | None = None,
    threshold: float = 0.0,
) -> list[tuple[str, float]]:
    """Score links by keyword relevance and return sorted (url, score) pairs above threshold."""
    neg = [k.lower() for k in (negative_keywords or [])]
    scored: list[tuple[str, float]] = []
    for url in links:
        score = _score_url(url, keywords, neg)
        if score >= threshold:
            scored.append((url, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def _score_url(url: str, keywords: list[str], neg_keywords: list[str]) -> float:
    lower = url.lower()
    # Penalise for negative keywords
    if any(nk in lower for nk in neg_keywords):
        return 0.0
    # Reward for positive keyword hits
    hits = sum(1 for kw in keywords if kw.lower() in lower)
    if not keywords:
        return 0.1
    base = hits / len(keywords)
    # Bonus for path depth (shallow pages often list pages)
    path = urlparse(url).path
    depth_bonus = 0.05 * min(path.count("/"), 4)
    return min(1.0, base + depth_bonus)
