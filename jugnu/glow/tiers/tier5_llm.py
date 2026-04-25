from __future__ import annotations

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter


class LlmAdapter(BaseAdapter):
    """Tier 5: LLM-based extraction — wired in Phase 6, stub here to keep import chain clean."""

    name = "llm"
    tier = 5

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        return bool(fetch_result.html)

    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        # Actual implementation wired in Phase 6 via jugnu.spark
        return AdapterResult(
            records=[],
            tier_used=self.name,
            confidence=0.0,
            error="llm_adapter_not_configured",
        )
