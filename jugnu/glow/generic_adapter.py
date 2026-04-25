from __future__ import annotations

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter
from jugnu.glow.tiers.tier1_json_ld import JsonLdAdapter
from jugnu.glow.tiers.tier2_api_json import ApiJsonAdapter
from jugnu.glow.tiers.tier3_microdata import MicrodataAdapter


class GenericAdapter(BaseAdapter):
    """Multi-tier adapter that tries deterministic tiers in order."""

    name = "generic"
    tier = 0

    def __init__(self) -> None:
        self._tiers: list[BaseAdapter] = [
            JsonLdAdapter(),
            ApiJsonAdapter(),
            MicrodataAdapter(),
        ]

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        return bool(fetch_result.html)

    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        for adapter in self._tiers:
            try:
                if await adapter.can_handle(fetch_result):
                    result = await adapter.extract(fetch_result, schema_fields)
                    if result.records:
                        return result
            except Exception:  # noqa: BLE001
                continue
        return AdapterResult(records=[], tier_used="generic", confidence=0.0)
