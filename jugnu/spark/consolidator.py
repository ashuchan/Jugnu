from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime

from jugnu.spark.prompts import render_template
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ConsolidationLogEntry, SkillMemory


class MemoryConsolidator:
    """Prompt-6: Consolidates pending ImprovementSignals into SkillMemory.

    Triggers (checked by crawler after each Blink):
      - batch_size: pending_signals >= settings.memory_consolidation_batch_size
      - smart_trigger: a new platform appears N times in pending_signals
      - run_end: crawl finished — consolidate remaining signals
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def consolidate(
        self,
        memory: SkillMemory,
        triggered_by: str = "batch",
        skill_name: str = "",
        general_instructions: str = "",
        output_fields: list[str] | None = None,
        minimum_fields: list[str] | None = None,
    ) -> SkillMemory:
        if not memory.pending_signals:
            return memory

        signals = memory.pending_signals[:]
        memory_snapshot = memory.model_dump(mode="json", exclude={"pending_signals"})
        success_count = sum(
            1 for s in signals if (s.confidence or 0.0) >= 0.5 and s.signal_type != "external_rank"
        )
        platforms_seen = sorted({s.platform for s in signals if s.platform})
        tiers = Counter(s.signal_type for s in signals)

        prompt = render_template(
            "consolidation",
            general_instructions=general_instructions or "(no instructions provided)",
            output_fields=", ".join(output_fields or []) or "(none)",
            minimum_fields=", ".join(minimum_fields or []) or "(none)",
            current_memory=json.dumps(memory_snapshot, indent=2, default=str),
            signals=json.dumps(
                [s.model_dump(mode="json") for s in signals], indent=2, default=str
            ),
            trigger=triggered_by,
            signal_count=len(signals),
            success_count=success_count,
            tier_distribution=", ".join(f"{k}={v}" for k, v in tiers.most_common()) or "(none)",
            platforms_seen=", ".join(platforms_seen) or "(none)",
        )
        response = await self._provider.complete(
            [{"role": "user", "content": prompt}],
            stage="prompt6_consolidation",
            skill=skill_name or memory.skill_name,
        )

        version_before = memory.memory_version
        cost = float(response.get("cost_usd") or 0.0)
        summary = ""

        if not response.get("error"):
            try:
                data = json.loads(response.get("content") or "")
                _apply(memory, data)
                summary = str(data.get("summary", ""))
            except json.JSONDecodeError:
                pass

        memory.memory_version += 1
        memory.total_consolidation_cost_usd += cost
        memory.pending_signals = []  # clear processed signals

        log_entry = ConsolidationLogEntry(
            triggered_by=triggered_by,
            signal_count=len(signals),
            signals_processed=len(signals),
            memory_version_before=version_before,
            memory_version_after=memory.memory_version,
            cost_usd=cost,
            timestamp=datetime.now(UTC).isoformat(),
            summary=summary,
        )
        memory.consolidation_log.append(log_entry)
        return memory

    def should_consolidate_batch(
        self,
        memory: SkillMemory,
        batch_size: int = 50,
    ) -> bool:
        return memory.pending_signal_count() >= batch_size

    def should_consolidate_smart(
        self,
        memory: SkillMemory,
        new_platform_confirmations: int = 0,
        trigger_count: int = 3,
    ) -> bool:
        return new_platform_confirmations >= trigger_count

    def count_new_platform_confirmations(self, memory: SkillMemory) -> int:
        """Number of times the most-frequent NEW platform appears in pending_signals.

        A platform is "new" if it is not yet a key in memory.platform_fingerprints.
        Used to drive the smart trigger.
        """
        known = set(memory.platform_fingerprints.keys())
        counts: Counter[str] = Counter()
        for s in memory.pending_signals:
            if s.platform and s.platform not in known:
                counts[s.platform] += 1
        return counts.most_common(1)[0][1] if counts else 0


def _apply(memory: SkillMemory, data: dict) -> None:
    if not isinstance(data, dict):
        return
    if "high_confidence_api_patterns" in data:
        memory.high_confidence_api_patterns = list(data["high_confidence_api_patterns"] or [])
    if "high_confidence_link_keywords" in data:
        memory.high_confidence_link_keywords = list(data["high_confidence_link_keywords"] or [])
    if "field_extraction_hints" in data:
        memory.field_extraction_hints = dict(data["field_extraction_hints"] or {})
    if "platform_fingerprints" in data:
        memory.platform_fingerprints = {
            k: list(v) for k, v in (data["platform_fingerprints"] or {}).items()
        }
    if "navigation_wisdom" in data:
        memory.navigation_wisdom = str(data["navigation_wisdom"] or "")
    if "confirmed_field_synonyms" in data:
        memory.confirmed_field_synonyms = {
            k: list(v) for k, v in (data["confirmed_field_synonyms"] or {}).items()
        }
    if "known_noise_patterns" in data:
        memory.known_noise_patterns = list(data["known_noise_patterns"] or [])
    if "prompt1_context" in data:
        memory.prompt1_context = str(data["prompt1_context"] or "")
    if "prompt2_context" in data:
        memory.prompt2_context = str(data["prompt2_context"] or "")
    if "prompt4_context" in data:
        memory.prompt4_context = str(data["prompt4_context"] or "")
