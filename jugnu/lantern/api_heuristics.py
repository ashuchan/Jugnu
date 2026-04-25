"""Domain-agnostic API/data-source heuristics.

No hardcoded vocabulary. Generic `looks_like_data_api` and `response_has_records`
take SkillMemory + OutputSchema fields and decide based on data shape, not
domain-specific words.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable

_API_PATH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"/api/", re.I),
    re.compile(r"/v\d+/", re.I),
    re.compile(r"\.json(\?|$)", re.I),
    re.compile(r"/graphql", re.I),
    re.compile(r"/feed(\b|/|\?)", re.I),
    re.compile(r"/rss(\b|/|\?)", re.I),
    re.compile(r"/sitemap", re.I),
    re.compile(r"/data/", re.I),
    re.compile(r"/search\?", re.I),
    re.compile(r"/listings\?", re.I),
    re.compile(r"\.xml(\?|$)", re.I),
]

_API_CONTENT_TYPES = {
    "application/json",
    "application/ld+json",
    "application/xml",
    "text/xml",
    "application/atom+xml",
    "application/rss+xml",
    "application/x-ndjson",
    "application/vnd.api+json",
}


def looks_like_api_endpoint(url: str, content_type: str = "") -> bool:
    """Coarse signal that a URL is an API rather than HTML page."""
    ct = content_type.lower().split(";")[0].strip()
    if ct in _API_CONTENT_TYPES:
        return True
    return any(p.search(url) for p in _API_PATH_PATTERNS)


def looks_like_data_api(
    url: str,
    content_type: str = "",
    learned_patterns: Iterable[str] | None = None,
    noise_patterns: Iterable[str] | None = None,
) -> bool:
    """Combine generic detection with SkillMemory-learned patterns.

    A URL is a data API candidate if:
      - it does NOT match any noise_patterns, AND
      - it matches a learned high_confidence_api_pattern OR a generic API signal.
    """
    lowered = url.lower()
    for noise in noise_patterns or []:
        if noise and noise.lower() in lowered:
            return False
    for pat in learned_patterns or []:
        if pat and pat.lower() in lowered:
            return True
    return looks_like_api_endpoint(url, content_type)


def response_has_records(
    body: str | bytes,
    output_fields: Iterable[str],
    min_field_overlap: int = 1,
) -> bool:
    """Return True if the response body looks like it contains records that
    overlap with the output schema.

    Domain-agnostic: looks for any list-of-dicts whose dict keys (case-folded,
    snake-normalised) overlap with at least `min_field_overlap` of the
    output_fields. Considers exact matches and `key contains field` matches so
    that synonym discovery still has signal.
    """
    if not body:
        return False
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return False
    text = body.strip()
    if not text:
        return False
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return False

    field_set = {f.lower() for f in output_fields}
    if not field_set:
        return False

    return _scan_for_records(data, field_set, min_field_overlap)


def _scan_for_records(node: object, fields: set[str], min_overlap: int) -> bool:
    if isinstance(node, list):
        for item in node:
            if isinstance(item, dict) and _dict_overlaps(item, fields, min_overlap):
                return True
        # Recurse into nested lists too
        for item in node:
            if _scan_for_records(item, fields, min_overlap):
                return True
        return False
    if isinstance(node, dict):
        for value in node.values():
            if _scan_for_records(value, fields, min_overlap):
                return True
    return False


def _dict_overlaps(record: dict, fields: set[str], min_overlap: int) -> bool:
    keys = {str(k).lower() for k in record.keys()}
    direct = len(keys & fields)
    if direct >= min_overlap:
        return True
    # Soft match: a record key contains a field name (e.g. "monthly_rent" → "rent")
    soft = sum(1 for k in keys for f in fields if f and f in k)
    return soft >= min_overlap


def score_api_pattern(pattern: str, observed_urls: list[str]) -> float:
    """Return 0.0–1.0 confidence that a pattern matches observed API URLs."""
    if not observed_urls:
        return 0.0
    hits = sum(1 for u in observed_urls if pattern in u)
    return hits / len(observed_urls)
