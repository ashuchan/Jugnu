from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ConsolidationLogEntry, ImprovementSignal, SkillMemory


class MemoryConsolidator:
    """Prompt-6: Consolidates pending ImprovementSignals into SkillMemory."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def consolidate(
        self,
        memory: SkillMemory,
        triggered_by: str = "batch",
    ) -> SkillMemory:
        if not memory.pending_signals:
            return memory

        signals = memory.pending_signals[:]
        memory_snapshot = memory.model_dump(mode="json", exclude={"pending_signals"})

        prompt = f"""You are a SkillMemory consolidation assistant.

Current memory:
{json.dumps(memory_snapshot, indent=2)}

Pending improvement signals ({len(signals)} signals):
{json.dumps([s.model_dump(mode='json') for s in signals], indent=2)}

Task: Analyze the improvement signals and update the memory to improve future extractions.

Return a JSON object with:
- "high_confidence_api_patterns": list[str]
- "high_confidence_link_keywords": list[str]
- "field_extraction_hints": dict[str, str]
- "platform_fingerprints": dict[str, list[str]]
- "navigation_wisdom": str
- "confirmed_field_synonyms": dict[str, list[str]]
- "known_noise_patterns": list[str]
- "prompt1_context": str
- "prompt2_context": str
- "prompt4_context": str
- "summary": str

Return ONLY valid JSON. No markdown fences."""
        response = await self._provider.complete([{"role": "user", "content": prompt}])

        version_before = memory.memory_version
        cost = response.get("cost_usd", 0.0)
        summary = ""

        if not response.get("error"):
            try:
                data = json.loads(response["content"])
                memory.high_confidence_api_patterns = data.get(
                    "high_confidence_api_patterns", memory.high_confidence_api_patterns
                )
                memory.high_confidence_link_keywords = data.get(
                    "high_confidence_link_keywords", memory.high_confidence_link_keywords
                )
                memory.field_extraction_hints = data.get(
                    "field_extraction_hints", memory.field_extraction_hints
                )
                memory.platform_fingerprints = data.get(
                    "platform_fingerprints", memory.platform_fingerprints
                )
                memory.navigation_wisdom = data.get("navigation_wisdom", memory.navigation_wisdom)
                memory.confirmed_field_synonyms = data.get(
                    "confirmed_field_synonyms", memory.confirmed_field_synonyms
                )
                memory.known_noise_patterns = data.get(
                    "known_noise_patterns", memory.known_noise_patterns
                )
                memory.prompt1_context = data.get("prompt1_context", memory.prompt1_context)
                memory.prompt2_context = data.get("prompt2_context", memory.prompt2_context)
                memory.prompt4_context = data.get("prompt4_context", memory.prompt4_context)
                summary = data.get("summary", "")
            except Exception:  # noqa: BLE001
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
            timestamp=datetime.now(timezone.utc).isoformat(),
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
