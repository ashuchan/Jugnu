from __future__ import annotations

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.adapter_registry import AdapterRegistry
from jugnu.glow.generic_adapter import GenericAdapter


class GlowResolver:
    """Orchestrates the extraction cascade: registry adapters then generic fallback."""

    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self._registry = registry or AdapterRegistry()
        self._generic = GenericAdapter()

    def register(self, adapter: object) -> None:
        self._registry.register(adapter)  # type: ignore[arg-type]

    async def resolve(
        self,
        fetch_result: FetchResult,
        schema_fields: list[str],
    ) -> AdapterResult:
        # Try registered adapters first (sorted by tier)
        for adapter in self._registry.all_adapters():
            try:
                if await adapter.can_handle(fetch_result):
                    result = await adapter.extract(fetch_result, schema_fields)
                    if result.records:
                        return result
            except Exception:  # noqa: BLE001
                continue

        # Fall back to generic multi-tier
        result = await self._generic.extract(fetch_result, schema_fields)
        return result
