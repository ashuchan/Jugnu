"""Tier 1a — Profile mapping replay (zero LLM).

Replays an existing ScrapeProfile's confirmed selectors / API hints against the
current page. If the profile is mature and the patterns still match, this tier
returns records without ever invoking the LLM.

Three replay modes, in order:
  1. _replay_dom: walk DomHints.confirmed_selectors against fetched HTML.
  2. _replay_api_active: re-fetch the per-mapping api_url_pattern via httpx,
     apply response_envelope, walk json_paths. THIS is the cost-saving lever.
  3. _replay_api_inline: if the original fetch_result IS already JSON, walk it
     using the same json_paths logic without a network round-trip.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter
from jugnu.profile import LlmFieldMapping, ScrapeProfile


class ProfileReplayAdapter(BaseAdapter):
    name = "profile_replay"
    tier = 1

    def __init__(
        self,
        profile: ScrapeProfile | None = None,
        replay_timeout_seconds: float = 10.0,
    ) -> None:
        self.profile = profile
        self._replay_timeout = replay_timeout_seconds

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        if self.profile is None:
            return False
        if self.profile.dom_hints.confirmed_selectors:
            return True
        if self.profile.api_hints.confirmed_endpoints:
            return True
        # Per-field mapping replay is also fair game.
        return any(
            (m.api_url_pattern or m.dom_selector or m.json_paths)
            for m in self.profile.field_mappings
        )

    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        if self.profile is None:
            return AdapterResult(records=[], tier_used=self.name, confidence=0.0)
        records = self._replay_dom(fetch_result.html, schema_fields)
        if not records:
            records = await self._replay_api_active(fetch_result, schema_fields)
        if not records:
            records = self._replay_api_inline(fetch_result, schema_fields)
        if records:
            self._bump_success_counts(records, schema_fields)
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

        scopes: list = []
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

    async def _replay_api_active(
        self,
        fetch_result: FetchResult,
        fields: list[str],
    ) -> list[dict]:
        """Re-fetch each unique api_url_pattern, then walk json_paths per field.

        The url_pattern stored on the mapping may be a relative path or full URL.
        Falls back silently on any error — replay is best-effort.
        """
        if not self.profile:
            return []
        # Group fields by api_url_pattern so we issue one request per endpoint.
        by_endpoint: dict[str, list[LlmFieldMapping]] = {}
        for mapping in self.profile.field_mappings:
            if not mapping.api_url_pattern:
                continue
            if fields and mapping.field_name not in fields:
                continue
            by_endpoint.setdefault(mapping.api_url_pattern, []).append(mapping)
        if not by_endpoint:
            return []

        records_per_endpoint: list[list[dict]] = []
        async with httpx.AsyncClient(timeout=self._replay_timeout) as client:
            for endpoint_pattern, mappings in by_endpoint.items():
                target_url = self._resolve_endpoint(endpoint_pattern, fetch_result.url)
                if not target_url:
                    continue
                try:
                    resp = await client.get(target_url)
                except (httpx.HTTPError, httpx.InvalidURL):
                    continue
                if resp.status_code < 200 or resp.status_code >= 300:
                    continue
                try:
                    payload = resp.json()
                except (json.JSONDecodeError, ValueError):
                    continue
                envelope = next(
                    (m.response_envelope for m in mappings if m.response_envelope),
                    None,
                )
                items = _unwrap_envelope(payload, envelope)
                if not items:
                    continue
                records = _project_with_paths(items, mappings, fields)
                if records:
                    records_per_endpoint.append(records)
        # Flatten — multiple endpoints contribute parallel record streams that
        # the caller can merge by primary_key downstream.
        flat: list[dict] = []
        for chunk in records_per_endpoint:
            flat.extend(chunk)
        return flat

    def _replay_api_inline(self, fetch_result: FetchResult, fields: list[str]) -> list[dict]:
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

    def _resolve_endpoint(self, pattern: str, base_url: str) -> str | None:
        """Pattern may be: full URL, absolute path, or template with {placeholders}.

        We strip placeholders (no values to fill) and join against base_url.
        """
        if not pattern:
            return None
        # Drop simple {placeholder} segments — best-effort replay.
        cleaned = re.sub(r"\{[^}]+\}", "", pattern).rstrip("/?&")
        if cleaned.startswith(("http://", "https://")):
            return cleaned
        try:
            return urljoin(base_url, cleaned)
        except (TypeError, ValueError):
            return None

    def _bump_success_counts(self, records: list[dict], fields: list[str]) -> None:
        if not self.profile or not records:
            return
        produced_fields = {k for r in records if isinstance(r, dict) for k in r}
        for mapping in self.profile.field_mappings:
            if fields and mapping.field_name not in fields:
                continue
            if mapping.field_name in produced_fields:
                mapping.success_count += 1
                if mapping.confidence < 0.95:
                    mapping.confidence = min(0.95, mapping.confidence + 0.05)


def _unwrap_envelope(payload: Any, envelope: str | None) -> list[Any]:
    """Walk dot/slash-separated envelope path; return a list-of-items.

    None envelope → assume the payload itself is already the list.
    """
    if envelope:
        node: Any = payload
        for key in re.split(r"[./]", envelope):
            if not key:
                continue
            if isinstance(node, dict):
                node = node.get(key)
            else:
                node = None
                break
        if isinstance(node, list):
            return list(node)
        if isinstance(node, dict):
            return [node]
        return []
    if isinstance(payload, list):
        return list(payload)
    if isinstance(payload, dict):
        # Try first list-of-dicts inside the payload.
        for v in payload.values():
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                return list(v)
        return [payload]
    return []


def _project_with_paths(
    items: list[Any],
    mappings: list[LlmFieldMapping],
    fields: list[str],
) -> list[dict]:
    """For each item, build a record applying each mapping's json_paths[field]."""
    records: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        record: dict = {}
        for mapping in mappings:
            field = mapping.field_name
            if fields and field not in fields:
                continue
            path = (mapping.json_paths or {}).get(field) or mapping.extraction_hint
            value = _walk_json_path(item, path)
            if value is not None:
                record[field] = value
        if record:
            records.append(record)
    return records


def _walk_json_path(node: Any, path: str | None) -> Any:
    """Minimal JSONPath: dot/slash/bracket notation for keys and integer indices.

    Examples accepted: 'rent', 'pricing.monthly', 'units[0].price', 'a.b.c'.
    Returns None on any miss — replay must never raise.
    """
    if not path or node is None:
        return None
    cur: Any = node
    # Tokenise on . / and []. Empty tokens dropped.
    raw_tokens = re.split(r"[./]|\[(\d+)\]", path)
    tokens = [t for t in raw_tokens if t not in (None, "")]
    for token in tokens:
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(token)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(token)
        else:
            return None
    return cur


def _find_records(node: object, fields: list[str]) -> list[dict]:
    if isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
        keys = {k.lower() for d in node for k in d.keys()}
        if not fields or any(f.lower() in keys for f in fields):
            return list(node)
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
