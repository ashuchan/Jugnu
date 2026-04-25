"""Tier 1c — Embedded SSR blob extraction (__NEXT_DATA__, __NUXT__, etc.).

Many SPA frameworks embed the page's hydration state as a JSON blob inside a
<script> tag. If we can find a list-of-dicts in there whose keys overlap the
output schema, we extract zero-LLM, zero-network records.
"""
from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter

_BLOB_PATTERNS = [
    (re.compile(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S), "next_data"),
    (re.compile(r'window\.__NUXT__\s*=\s*(\{.*?\});', re.S), "nuxt"),
    (re.compile(r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\});', re.S), "apollo"),
    (re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', re.S), "initial_state"),
    (re.compile(r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});', re.S), "preloaded_state"),
]


class EmbeddedBlobAdapter(BaseAdapter):
    name = "embedded_blob"
    tier = 1

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        html = fetch_result.html or ""
        return any(p.search(html) for p, _ in _BLOB_PATTERNS)

    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        html = fetch_result.html or ""
        records: list[dict] = []
        source = ""
        for pattern, label in _BLOB_PATTERNS:
            match = pattern.search(html)
            if not match:
                continue
            blob = match.group(1).strip()
            data = _safe_json(blob)
            if data is None and label == "next_data":
                # Some sites HTML-encode the blob; fall back to BeautifulSoup.
                try:
                    soup = BeautifulSoup(html, "lxml")
                    tag = soup.find("script", id="__NEXT_DATA__")
                    if tag and tag.string:
                        data = _safe_json(tag.string)
                except Exception:  # noqa: BLE001
                    data = None
            if data is None:
                continue
            found = _find_records(data, schema_fields)
            if found:
                records = found
                source = label
                break
        confidence = 0.8 if records else 0.0
        return AdapterResult(
            records=records,
            tier_used=f"{self.name}:{source}" if source else self.name,
            confidence=confidence,
        )


def _safe_json(text: str) -> object | None:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _find_records(node: object, fields: list[str]) -> list[dict]:
    if isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
        keys = {k.lower() for d in node for k in d.keys()}
        if not fields or any(f.lower() in keys for f in fields):
            return list(node)  # type: ignore[arg-type]
    if isinstance(node, dict):
        for v in node.values():
            found = _find_records(v, fields)
            if found:
                return found
    if isinstance(node, list):
        for v in node:
            found = _find_records(v, fields)
            if found:
                return found
    return []
