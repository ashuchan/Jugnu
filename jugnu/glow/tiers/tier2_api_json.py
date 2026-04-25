from __future__ import annotations

import json

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter


class ApiJsonAdapter(BaseAdapter):
    name = "api_json"
    tier = 2

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        ct = fetch_result.content_type.lower()
        return "application/json" in ct or "json" in ct

    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        records: list[dict] = []
        try:
            data = json.loads(fetch_result.html or fetch_result.text)
            if isinstance(data, list):
                records = [r for r in data if isinstance(r, dict)]
            elif isinstance(data, dict):
                # Try to find a list inside the response
                for v in data.values():
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        records = v
                        break
                if not records:
                    records = [data]
        except Exception:  # noqa: BLE001
            pass
        return AdapterResult(
            records=records,
            tier_used=self.name,
            confidence=0.85 if records else 0.0,
        )
