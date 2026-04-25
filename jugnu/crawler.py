from __future__ import annotations

import asyncio
from pathlib import Path

from jugnu.contracts import Blink, CrawlInput, CrawlStatus
from jugnu.dlq import DeadLetterQueue
from jugnu.ember.fetcher import Ember
from jugnu.ember.rate_limiter import RateLimiter
from jugnu.glow.resolver import GlowResolver
from jugnu.glow.schema_normalizer import normalize_record
from jugnu.lantern.discovery import Lantern
from jugnu.observability.cost_ledger import CostLedger
from jugnu.observability.trace import EventKind, configure_sink, emit
from jugnu.profile import ScrapeProfile
from jugnu.profile_store import ProfileStore
from jugnu.profile_updater import ProfileUpdater
from jugnu.skill import Skill
from jugnu.spark.consolidator import MemoryConsolidator
from jugnu.spark.crystallizer import crystallize
from jugnu.spark.discovery_llm import DiscoveryLLM
from jugnu.spark.external_ranker_llm import ExternalRankerLLM
from jugnu.spark.extraction_llm import ExtractionLLM
from jugnu.spark.merge_llm import MergeLLM
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory
from jugnu.spark.warmup import WarmupOrchestrator
from jugnu.validation.identity_fallback import assign_identities
from jugnu.validation.schema_gate import passes_schema_gate


class Jugnu:
    """Main orchestrator: warm-up + concurrency-bounded crawl loop.

    Per-URL pipeline:
      1. Fetch via Ember (carry-forward on failure when prior records exist).
      2. Deterministic extraction via Glow tier cascade.
      3. If empty: Prompt-2 LLM extraction.
      4. If still missing minimum_fields and max_external_depth > 0: Prompt-4 ranks
         external links (the actual crawl of those links is left to the caller — we
         emit ranked candidates in blink.metadata).
      5. If CrawlInput.previous_records is non-empty AND new records exist:
         Prompt-3 merge resolves new vs existing.
      6. Profile update + identity assignment + schema gate.
      7. _maybe_consolidate: Prompt-6 fires on batch / smart trigger.

    Run-end: any remaining pending_signals are consolidated with trigger='run_end'.
    Every Blink carries blink.llm_profile = the (mutated) SkillMemory.
    """

    def __init__(
        self,
        skill: Skill,
        skill_memory: SkillMemory | None = None,
        profile_store: ProfileStore | None = None,
        cost_ledger_path: str | Path | None = None,
        trace_path: str | Path | None = None,
    ) -> None:
        self._skill = skill
        self._memory = skill_memory
        self._profile_store = profile_store or ProfileStore()
        self._provider = LLMProvider.from_settings(skill.llm_settings)
        self._warmup = WarmupOrchestrator(self._provider)
        self._discovery = DiscoveryLLM(self._provider)
        self._extractor = ExtractionLLM(self._provider)
        self._merger = MergeLLM(self._provider)
        self._external_ranker = ExternalRankerLLM(self._provider)
        self._consolidator = MemoryConsolidator(self._provider)
        self._updater = ProfileUpdater()
        self._dlq = DeadLetterQueue()
        self._cost_ledger: CostLedger | None = (
            CostLedger(cost_ledger_path) if cost_ledger_path else None
        )
        if self._cost_ledger is not None:
            self._provider.attach_ledger(self._cost_ledger)
        if trace_path is not None:
            configure_sink(trace_path)
        self._consolidations_fired = 0

    @classmethod
    def from_settings(cls, settings: object) -> LLMProvider:  # pragma: no cover - legacy shim
        return LLMProvider.from_settings(settings)

    @property
    def cost_ledger(self) -> CostLedger | None:
        return self._cost_ledger

    @property
    def dlq(self) -> DeadLetterQueue:
        return self._dlq

    @property
    def skill_memory(self) -> SkillMemory | None:
        return self._memory

    async def warm_up(self) -> SkillMemory:
        self._memory = await self._warmup.warm_up(
            skill_name=self._skill.name,
            skill_version=self._skill.version,
            skill_description=self._skill.description,
            output_fields=self._skill.output_schema.fields,
            minimum_fields=self._skill.output_schema.minimum_fields,
            general_instructions=self._skill.custom_instructions,
            source_hints=[h.model_dump(mode="json") for h in self._skill.source_hints],
            existing_memory=self._memory,
        )
        emit(
            EventKind.WARMUP_COMPLETE,
            skill=self._skill.name,
            memory_version=self._memory.memory_version,
            cost_usd=self._memory.warmup_cost_usd,
        )
        return self._memory

    async def crawl(self, inputs: dict[str, CrawlInput]) -> dict[str, Blink]:
        if self._memory is None or self._memory.is_stale_for(self._skill):
            await self.warm_up()
        emit(EventKind.CRAWL_STARTED, skill=self._skill.name, url_count=len(inputs))
        max_concurrency = self._skill.jugnu_settings.max_concurrent_crawls
        sem = asyncio.Semaphore(max_concurrency if max_concurrency > 0 else max(1, len(inputs)))
        results: dict[str, Blink] = {}

        async def _crawl_one(url: str, inp: CrawlInput) -> None:
            async with sem:
                blink = await self._crawl_url(url, inp)
                results[url] = blink
                await self._maybe_consolidate()

        await asyncio.gather(*[_crawl_one(url, inp) for url, inp in inputs.items()])

        if self._memory and self._memory.pending_signal_count() > 0:
            self._memory = await self._consolidator.consolidate(
                self._memory,
                triggered_by="run_end",
                skill_name=self._skill.name,
                general_instructions=self._skill.custom_instructions,
                output_fields=self._skill.output_schema.fields,
                minimum_fields=self._skill.output_schema.minimum_fields,
            )
            self._consolidations_fired += 1
            emit(
                EventKind.CONSOLIDATION_FIRED,
                skill=self._skill.name,
                trigger="run_end",
                memory_version=self._memory.memory_version,
            )

        for blink in results.values():
            blink.llm_profile = self._memory

        emit(
            EventKind.CRAWL_COMPLETED,
            skill=self._skill.name,
            url_count=len(results),
            consolidations=self._consolidations_fired,
        )
        return results

    async def _crawl_url(self, url: str, inp: CrawlInput) -> Blink:
        errors: list[str] = []
        prior_records = list(inp.previous_records or [])
        carry_records = list(inp.carry_forward_records or prior_records)
        try:
            rate_limiter = RateLimiter(requests_per_second=1.0, burst=3)
            ember = Ember(rate_limiter=rate_limiter, timeout_ms=30_000, max_retries=1)
            fetch_result = await ember.fetch(url)

            if not fetch_result.success:
                if self._skill.jugnu_settings.carry_forward_on_failure and carry_records:
                    emit(EventKind.CARRY_FORWARD, url=url, skill=self._skill.name)
                    return Blink(
                        url=url,
                        status=CrawlStatus.CARRY_FORWARD,
                        records=carry_records,
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

            # Glow: deterministic extraction first, informed by profile + SkillMemory
            existing_profile = (
                inp.scrape_profile
                or self._profile_store.load(url)
            )
            resolver = GlowResolver()
            adapter_result = await resolver.resolve(
                fetch_result,
                self._skill.output_schema.fields,
                profile=existing_profile,
                learned_api_patterns=(
                    self._memory.high_confidence_api_patterns if self._memory else None
                ),
                noise_patterns=(
                    self._memory.known_noise_patterns if self._memory else None
                ),
            )
            emit(
                EventKind.TIER_ATTEMPTED,
                url=url,
                skill=self._skill.name,
                tier=adapter_result.tier_used,
                records=len(adapter_result.records),
            )

            records = adapter_result.records
            tier = adapter_result.tier_used
            confidence = adapter_result.confidence
            llm_cost = adapter_result.llm_cost_usd

            # Prompt-2 LLM extraction if deterministic came back empty.
            llm_field_mappings: dict | None = None
            llm_field_mapping_notes = ""
            if not records:
                llm_result = await self._extractor.extract(
                    fetch_result=fetch_result,
                    fields=self._skill.output_schema.fields,
                    minimum_fields=self._skill.output_schema.minimum_fields,
                    output_schema=self._skill.output_schema.model_dump(mode="json"),
                    memory=self._memory,
                    general_instructions=self._skill.custom_instructions,
                    custom_instructions=self._skill.custom_instructions,
                    skill_name=self._skill.name,
                )
                records = llm_result.get("records") or []
                tier = "llm_extraction"
                confidence = float(llm_result.get("confidence") or 0.0)
                llm_cost += float(llm_result.get("cost_usd") or 0.0)
                llm_field_mappings = llm_result.get("field_mappings") or None
                llm_field_mapping_notes = llm_result.get("field_mapping_notes", "")
                self._record_signal(llm_result.get("improvement_signal"))

            # Normalise field names against confirmed synonyms before downstream steps.
            synonyms = (self._memory.confirmed_field_synonyms if self._memory else None) or None
            if synonyms:
                records = [normalize_record(r, synonyms) for r in records if isinstance(r, dict)]

            # Prompt-4 external rank if minimum fields still unmet.
            external_candidates: list[dict] = []
            settings = self._skill.jugnu_settings
            missing_fields = self._missing_minimum_fields(records)
            if missing_fields and settings.max_external_depth > 0:
                mem_keywords = self._memory.high_confidence_link_keywords if self._memory else None
                mem_api_patterns = (
                    self._memory.high_confidence_api_patterns if self._memory else None
                )
                lantern = Lantern(
                    keywords=mem_keywords,
                    api_patterns=mem_api_patterns,
                )
                discovered = lantern.discover(fetch_result)
                external_links = [
                    {"url": link, "score": score}
                    for link, score in discovered.ranked_links[:25]
                ]
                if external_links:
                    ext_result = await self._external_ranker.rank_external(
                        general_instructions=self._skill.custom_instructions,
                        output_fields=self._skill.output_schema.fields,
                        missing_fields=missing_fields,
                        extracted_records=records,
                        external_links=external_links,
                        current_depth=0,
                        max_depth=settings.max_external_depth,
                        memory=self._memory,
                        url=url,
                        skill_name=self._skill.name,
                    )
                    external_candidates = ext_result.get("ranked_external_links") or []
                    llm_cost += float(ext_result.get("cost_usd") or 0.0)
                    self._record_signal(ext_result.get("improvement_signal"))
                    if external_candidates:
                        emit(
                            EventKind.EXTERNAL_RANK_INVOKED,
                            url=url,
                            skill=self._skill.name,
                            candidate_count=len(external_candidates),
                        )

            emit(
                EventKind.TIER_WON,
                url=url,
                skill=self._skill.name,
                tier=tier,
                records=len(records),
                confidence=confidence,
            )

            # Prompt-3 merge mode: only if caller passed previous_records AND we have new ones.
            merge_decisions: list[dict] = []
            if prior_records and records:
                merge_result = await self._merger.merge(
                    existing_records=prior_records,
                    new_records=records,
                    primary_key=self._skill.output_schema.primary_key,
                    merging_keys=self._skill.output_schema.merging_keys,
                    general_instructions=self._skill.custom_instructions,
                    memory=self._memory,
                    url=url,
                    skill_name=self._skill.name,
                    output_fields=self._skill.output_schema.fields,
                    minimum_fields=self._skill.output_schema.minimum_fields,
                )
                merge_decisions = merge_result.get("merge_decisions") or []
                llm_cost += float(merge_result.get("cost_usd") or 0.0)
                if merge_result.get("merged_records"):
                    records = merge_result["merged_records"]
                emit(
                    EventKind.MERGE_INVOKED,
                    url=url,
                    skill=self._skill.name,
                    added=merge_result.get("added_count", 0),
                    updated=merge_result.get("updated_count", 0),
                )

            # Identity + schema gate
            records = assign_identities(records, self._skill.output_schema.primary_key)
            passes, _ = passes_schema_gate(records, self._skill.output_schema)
            status = CrawlStatus.SUCCESS if passes else CrawlStatus.PARTIAL
            if not records:
                status = CrawlStatus.EMPTY

            # Profile update — reuse the one we loaded for the cascade.
            profile = existing_profile or ScrapeProfile(url_pattern=url)
            if llm_field_mappings:
                crystallize(profile, llm_field_mappings, llm_field_mapping_notes)
            self._updater.record_success(profile, len(records), confidence, fetch_result.latency_ms)
            self._profile_store.save(profile)
            emit(
                EventKind.PROFILE_UPDATED,
                url=url,
                skill=self._skill.name,
                maturity=str(profile.maturity),
            )

            blink = Blink(
                url=url,
                status=status,
                records=records,
                tier_used=tier,
                confidence=confidence,
                llm_cost_usd=llm_cost,
                errors=errors,
                llm_profile=self._memory,
                scrape_profile=profile,
            )
            if external_candidates or merge_decisions:
                blink.llm_interactions.append(
                    {
                        "external_candidates": external_candidates,
                        "merge_decisions": merge_decisions,
                    }
                )
            return blink
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            self._dlq.push(url, str(exc))
            emit(EventKind.DLQ_PUSH, url=url, skill=self._skill.name, reason=str(exc))
            if self._skill.jugnu_settings.carry_forward_on_failure and carry_records:
                return Blink(
                    url=url,
                    status=CrawlStatus.CARRY_FORWARD,
                    records=carry_records,
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

    def _record_signal(self, signal: object) -> None:
        if isinstance(signal, ImprovementSignal) and self._memory is not None:
            self._memory.add_signal(signal)

    def _missing_minimum_fields(self, records: list[dict]) -> list[str]:
        required = self._skill.output_schema.minimum_fields or []
        if not required:
            return []
        if not records:
            return list(required)
        missing: list[str] = []
        for field in required:
            if all((rec.get(field) in (None, "")) for rec in records):
                missing.append(field)
        return missing

    async def _maybe_consolidate(self) -> None:
        if self._memory is None:
            return
        settings = self._skill.jugnu_settings
        if self._consolidator.should_consolidate_batch(
            self._memory, settings.memory_consolidation_batch_size
        ):
            self._memory = await self._consolidator.consolidate(
                self._memory,
                triggered_by="batch",
                skill_name=self._skill.name,
                general_instructions=self._skill.custom_instructions,
                output_fields=self._skill.output_schema.fields,
                minimum_fields=self._skill.output_schema.minimum_fields,
            )
            self._consolidations_fired += 1
            emit(
                EventKind.CONSOLIDATION_FIRED,
                skill=self._skill.name,
                trigger="batch",
                memory_version=self._memory.memory_version,
            )
            return
        new_platform_count = self._consolidator.count_new_platform_confirmations(self._memory)
        if self._consolidator.should_consolidate_smart(
            self._memory,
            new_platform_confirmations=new_platform_count,
            trigger_count=settings.memory_consolidation_smart_trigger_count,
        ):
            emit(
                EventKind.SMART_TRIGGER_DETECTED,
                skill=self._skill.name,
                new_platform_confirmations=new_platform_count,
            )
            self._memory = await self._consolidator.consolidate(
                self._memory,
                triggered_by="smart_trigger",
                skill_name=self._skill.name,
                general_instructions=self._skill.custom_instructions,
                output_fields=self._skill.output_schema.fields,
                minimum_fields=self._skill.output_schema.minimum_fields,
            )
            self._consolidations_fired += 1
            emit(
                EventKind.CONSOLIDATION_FIRED,
                skill=self._skill.name,
                trigger="smart_trigger",
                memory_version=self._memory.memory_version,
            )
