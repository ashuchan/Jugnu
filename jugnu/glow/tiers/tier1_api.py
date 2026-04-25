"""Tier 1b — Known API heuristic parse.

Given a SkillMemory or SourceHint listing high-confidence API URL patterns, this
adapter recognises a JSON response that matches one of those patterns and
returns the records directly. Pure deterministic — no LLM.
"""
from __future__ import annotations

import json
from collections.abc import Iterable

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter
from jugnu.lantern.api_heuristics import looks_like_data_api, response_has_records


class KnownApiAdapter(BaseAdapter):
    name = "known_api"
    tier = 1

    def __init__(
        self,
        learned_patterns: Iterable[str] | None = None,
        noise_patterns: Iterable[str] | None = None,
        blocked_endpoints: Iterable[str] | None = None,
    ) -> None:
        self._learned = list(learned_patterns or [])
        self._noise = list(noise_patterns or [])
        self._blocked = list(blocked_endpoints or [])

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        # Per-URL ScrapeProfile.api_hints.blocked_endpoints short-circuits before
        # any heuristic check — caller learned this endpoint produces noise.
        if any(b and b in fetch_result.url for b in self._blocked):
            return False
        if not looks_like_data_api(
            fetch_result.url,
            content_type=fetch_result.content_type,
            learned_patterns=self._learned,
            noise_patterns=self._noise,
        ):
            return False
        body = fetch_result.html or fetch_result.text or ""
        return bool(body)

    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        body = fetch_result.html or fetch_result.text or ""
        if not response_has_records(body, schema_fields):
            return AdapterResult(records=[], tier_used=self.name, confidence=0.0)
        records = _records_from_json(body, schema_fields)
        return AdapterResult(
            records=records,
            tier_used=self.name,
            confidence=0.9 if records else 0.0,
        )


def _records_from_json(body: str, fields: list[str]) -> list[dict]:
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return []
    return _walk(data, fields)


def _walk(node: object, fields: list[str]) -> list[dict]:
    if isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
        keys = {k.lower() for d in node for k in d.keys()}
        if not fields or any(f.lower() in keys for f in fields):
            return list(node)  # type: ignore[arg-type]
    if isinstance(node, dict):
        for v in node.values():
            found = _walk(v, fields)
            if found:
                return found
    if isinstance(node, list):
        for v in node:
            found = _walk(v, fields)
            if found:
                return found
    return []
