from __future__ import annotations

from collections.abc import Iterable

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter
from jugnu.glow.tiers.tier1_api import KnownApiAdapter
from jugnu.glow.tiers.tier1_embedded import EmbeddedBlobAdapter
from jugnu.glow.tiers.tier1_json_ld import JsonLdAdapter
from jugnu.glow.tiers.tier1_profile import ProfileReplayAdapter
from jugnu.glow.tiers.tier2_api_json import ApiJsonAdapter
from jugnu.glow.tiers.tier3_microdata import MicrodataAdapter
from jugnu.profile import ScrapeProfile


class GenericAdapter(BaseAdapter):
    """Multi-tier adapter that tries deterministic tiers in order.

    Tier order (highest priority first):
      1a) Profile replay (zero LLM, when profile is provided)
      1b) Known API match (matches SkillMemory.high_confidence_api_patterns)
      1c) Embedded SSR blobs (__NEXT_DATA__, __NUXT__, etc.)
      1d) JSON-LD / Schema.org
      2)  Bare JSON response
      3)  Microdata
    """

    name = "generic"
    tier = 0

    def __init__(
        self,
        profile: ScrapeProfile | None = None,
        learned_api_patterns: Iterable[str] | None = None,
        noise_patterns: Iterable[str] | None = None,
    ) -> None:
        # Per-URL blocked endpoints (gap 6) — learned from prior runs that this
        # specific endpoint returns noise. Hands the list to KnownApiAdapter so
        # it short-circuits before re-trying the noisy URL.
        per_url_blocked = (
            list(profile.api_hints.blocked_endpoints) if profile else []
        )
        self._tiers: list[BaseAdapter] = [
            ProfileReplayAdapter(profile=profile),
            KnownApiAdapter(
                learned_patterns=learned_api_patterns,
                noise_patterns=noise_patterns,
                blocked_endpoints=per_url_blocked,
            ),
            EmbeddedBlobAdapter(),
            JsonLdAdapter(),
            ApiJsonAdapter(),
            MicrodataAdapter(),
        ]

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        return bool(fetch_result.html or fetch_result.text)

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
