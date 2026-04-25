from __future__ import annotations

import asyncio
from typing import Optional

from jugnu.contracts import Blink, CrawlInput, CrawlStatus
from jugnu.dlq import DeadLetterQueue
from jugnu.ember.fetcher import Ember
from jugnu.ember.rate_limiter import RateLimiter
from jugnu.glow.resolver import GlowResolver
from jugnu.lantern.discovery import Lantern
from jugnu.profile import ScrapeProfile
from jugnu.profile_store import ProfileStore
from jugnu.profile_updater import ProfileUpdater
from jugnu.skill import Skill
from jugnu.spark.consolidator import MemoryConsolidator
from jugnu.spark.extraction_llm import ExtractionLLM
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory
from jugnu.spark.warmup import WarmupOrchestrator
from jugnu.validation.cross_run_sanity import sanity_check
from jugnu.validation.identity_fallback import assign_identities
from jugnu.validation.schema_gate import passes_schema_gate


class Jugnu:
    """Main orchestrator: warm-up + concurrency-bounded crawl loop."""

    def __init__(
        self,
        skill: Skill,
        skill_memory: Optional[SkillMemory] = None,
        profile_store: Optional[ProfileStore] = None,
    ) -> None:
        self._skill = skill
        self._memory = skill_memory
        self._profile_store = profile_store or ProfileStore()
        self._provider = LLMProvider.from_settings(skill.llm_settings)
        self._warmup = WarmupOrchestrator(self._provider)
        self._extractor = ExtractionLLM(self._provider)
        self._consolidator = MemoryConsolidator(self._provider)
        self._updater = ProfileUpdater()
        self._dlq = DeadLetterQueue()

    async def warm_up(self) -> SkillMemory:
        self._memory = await self._warmup.warm_up(
            skill_name=self._skill.name,
            skill_version=self._skill.version,
            skill_description=self._skill.description,
            output_fields=self._skill.output_schema.fields,
            source_hints=[h.model_dump(mode="json") for h in self._skill.source_hints],
            existing_memory=self._memory,
        )
        return self._memory

    async def crawl(
        self,
        inputs: dict[str, CrawlInput],
    ) -> dict[str, Blink]:
        max_concurrency = self._skill.jugnu_settings.max_concurrent_crawls
        sem = asyncio.Semaphore(max_concurrency if max_concurrency > 0 else len(inputs))
        results: dict[str, Blink] = {}

        async def _crawl_one(url: str, inp: CrawlInput) -> None:
            async with sem:
                blink = await self._crawl_url(url, inp)
                results[url] = blink
                self._maybe_consolidate()

        await asyncio.gather(*[_crawl_one(url, inp) for url, inp in inputs.items()])

        # Run-end consolidation
        if self._memory and self._memory.pending_signal_count() > 0:
            self._memory = await self._consolidator.consolidate(
                self._memory, triggered_by="run_end"
            )

        for blink in results.values():
            blink.llm_profile = self._memory
        return results

    async def _crawl_url(self, url: str, inp: CrawlInput) -> Blink:
        errors: list[str] = []
        try:
            rate_limiter = RateLimiter(
                requests_per_second=1.0, burst=3
            )
            ember = Ember(rate_limiter=rate_limiter, timeout_ms=30_000, max_retries=1)
            fetch_result = await ember.fetch(url)

            if not fetch_result.success:
                if self._skill.jugnu_settings.carry_forward_on_failure and inp.carry_forward_records:
                    return Blink(
                        url=url,
                        status=CrawlStatus.CARRY_FORWARD,
                        records=list(inp.carry_forward_records),
                        carry_forward_days=7,
                        errors=[fetch_result.error or "fetch_failed"],
                        llm_profile=self._memory,
                    )
                return Blink(
                    url=url,
                    status=CrawlStatus.FAILED,
                    records=[],
                    errors=[fetch_result.error or "fetch_failed"],
                    llm_profile=self._memory,
                )

            # Glow: deterministic extraction first
            resolver = GlowResolver()
            adapter_result = await resolver.resolve(fetch_result, self._skill.output_schema.fields)

            records = adapter_result.records
            tier = adapter_result.tier_used
            confidence = adapter_result.confidence

            # LLM extraction if deterministic came back empty
            if not records:
                llm_result = await self._extractor.extract(
                    fetch_result=fetch_result,
                    fields=self._skill.output_schema.fields,
                    memory=self._memory,
                    custom_instructions=self._skill.custom_instructions,
                )
                records = llm_result.get("records", [])
                tier = "llm"
                confidence = llm_result.get("confidence", 0.0)
                sig = llm_result.get("improvement_signal")
                if sig and isinstance(sig, ImprovementSignal) and self._memory:
                    self._memory.add_signal(sig)

            # Assign identities + validate
            records = assign_identities(records, self._skill.output_schema.primary_key)
            passes, _ = passes_schema_gate(records, self._skill.output_schema)
            status = CrawlStatus.SUCCESS if passes else CrawlStatus.PARTIAL

            # Update profile
            profile = self._profile_store.load(url) or ScrapeProfile(url_pattern=url)
            self._updater.record_success(profile, len(records), confidence, fetch_result.latency_ms)
            self._profile_store.save(profile)

            return Blink(
                url=url,
                status=status,
                records=records,
                tier_used=tier,
                confidence=confidence,
                llm_cost_usd=adapter_result.llm_cost_usd,
                errors=errors,
                llm_profile=self._memory,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            self._dlq.push(url, str(exc))
            if self._skill.jugnu_settings.carry_forward_on_failure and inp.carry_forward_records:
                return Blink(
                    url=url,
                    status=CrawlStatus.CARRY_FORWARD,
                    records=list(inp.carry_forward_records),
                    carry_forward_days=7,
                    errors=errors,
                    llm_profile=self._memory,
                )
            return Blink(
                url=url,
                status=CrawlStatus.FAILED,
                records=[],
                errors=errors,
                llm_profile=self._memory,
            )

    def _maybe_consolidate(self) -> None:
        if self._memory is None:
            return
        settings = self._skill.jugnu_settings
        if self._consolidator.should_consolidate_batch(
            self._memory, settings.memory_consolidation_batch_size
        ):
            # Fire-and-forget in the background; will be awaited at run-end
            asyncio.create_task(  # noqa: RUF006
                self._consolidator.consolidate(self._memory, triggered_by="batch")
            )

    @property
    def dlq(self) -> DeadLetterQueue:
        return self._dlq
