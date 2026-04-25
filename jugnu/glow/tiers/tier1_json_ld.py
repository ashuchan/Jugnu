from __future__ import annotations

import json

from bs4 import BeautifulSoup

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter


class JsonLdAdapter(BaseAdapter):
    name = "json_ld"
    tier = 1

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        return "application/ld+json" in fetch_result.html

    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        records: list[dict] = []
        try:
            soup = BeautifulSoup(fetch_result.html, "lxml")
            for tag in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(tag.string or "")
                    if isinstance(data, list):
                        records.extend(data)
                    elif isinstance(data, dict):
                        records.append(data)
                except json.JSONDecodeError:
                    pass
        except Exception:  # noqa: BLE001
            pass
        return AdapterResult(
            records=records,
            tier_used=self.name,
            confidence=0.9 if records else 0.0,
        )
