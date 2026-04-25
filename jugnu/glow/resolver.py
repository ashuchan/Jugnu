from __future__ import annotations

from collections.abc import Iterable

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.adapter_registry import AdapterRegistry
from jugnu.glow.generic_adapter import GenericAdapter
from jugnu.profile import ScrapeProfile


class GlowResolver:
    """Orchestrates the extraction cascade: registered platform adapters first,
    then a SkillMemory- and profile-aware generic cascade.
    """

    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self._registry = registry or AdapterRegistry()

    def register(self, adapter: object) -> None:
        self._registry.register(adapter)  # type: ignore[arg-type]

    async def resolve(
        self,
        fetch_result: FetchResult,
        schema_fields: list[str],
        profile: ScrapeProfile | None = None,
        learned_api_patterns: Iterable[str] | None = None,
        noise_patterns: Iterable[str] | None = None,
    ) -> AdapterResult:
        # Try registered platform-specific adapters first (sorted by tier)
        for adapter in self._registry.all_adapters():
            try:
                if await adapter.can_handle(fetch_result):
                    result = await adapter.extract(fetch_result, schema_fields)
                    if result.records:
                        return result
            except Exception:  # noqa: BLE001
                continue

        # SkillMemory-aware generic cascade
        generic = GenericAdapter(
            profile=profile,
            learned_api_patterns=learned_api_patterns,
            noise_patterns=noise_patterns,
        )
        return await generic.extract(fetch_result, schema_fields)
