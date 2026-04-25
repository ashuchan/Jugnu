"""Tier 1a — Profile mapping replay (zero LLM).

Replays an existing ScrapeProfile's confirmed selectors / API hints against the
current page. If the profile is mature and the patterns still match, this tier
returns records without ever invoking the LLM.
"""
from __future__ import annotations

import json

from bs4 import BeautifulSoup

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter
from jugnu.profile import ScrapeProfile


class ProfileReplayAdapter(BaseAdapter):
    name = "profile_replay"
    tier = 1

    def __init__(self, profile: ScrapeProfile | None = None) -> None:
        self.profile = profile

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        return self.profile is not None and bool(
            self.profile.dom_hints.confirmed_selectors
            or self.profile.api_hints.confirmed_endpoints
        )

    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        if self.profile is None:
            return AdapterResult(records=[], tier_used=self.name, confidence=0.0)
        records = self._replay_dom(fetch_result.html, schema_fields)
        if not records:
            records = self._replay_api(fetch_result, schema_fields)
        confidence = 0.85 if records else 0.0
        return AdapterResult(records=records, tier_used=self.name, confidence=confidence)

    def _replay_dom(self, html: str, fields: list[str]) -> list[dict]:
        if not self.profile or not html:
            return []
        selectors = self.profile.dom_hints.confirmed_selectors
        containers = self.profile.dom_hints.list_container_selectors
        if not selectors:
            return []
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:  # noqa: BLE001
            return []

        scopes = []
        for sel in containers:
            scopes.extend(soup.select(sel))
        if not scopes:
            scopes = [soup]

        records: list[dict] = []
        for scope in scopes:
            record: dict = {}
            for field, css in selectors.items():
                if fields and field not in fields:
                    continue
                try:
                    el = scope.select_one(css)
                except Exception:  # noqa: BLE001
                    continue
                if el is None:
                    continue
                value = el.get("content") or el.get_text(strip=True)
                if value:
                    record[field] = value
            if record:
                records.append(record)
        return records

    def _replay_api(self, fetch_result: FetchResult, fields: list[str]) -> list[dict]:
        if not self.profile or not fetch_result.html:
            return []
        ct = (fetch_result.content_type or "").lower()
        if "json" not in ct:
            return []
        try:
            data = json.loads(fetch_result.html)
        except json.JSONDecodeError:
            return []
        # Walk the JSON and pick the first list-of-dicts whose keys overlap fields.
        return _find_records(data, fields)


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
