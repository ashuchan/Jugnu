from __future__ import annotations

import json
from typing import Optional

from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory


class MergeLLM:
    """Prompt-4: Merge and deduplicate records using LLM reasoning."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def merge(
        self,
        existing_records: list[dict],
        new_records: list[dict],
        primary_key: Optional[str],
        merging_keys: list[str],
        memory: Optional[SkillMemory] = None,
    ) -> dict:
        memory_ctx = memory.prompt4_context if memory else ""
        prompt = f"""You are a data merge and deduplication assistant.

Existing records ({len(existing_records)} records):
{json.dumps(existing_records[:20], indent=2)}

New records ({len(new_records)} records):
{json.dumps(new_records[:20], indent=2)}

Primary key: {primary_key or 'none'}
Merging keys: {', '.join(merging_keys) if merging_keys else 'none'}
Memory context: {memory_ctx}

Task: Merge new records into existing, deduplicating by primary/merging keys.

Return a JSON object with:
- "merged_records": list[dict]
- "added_count": int
- "updated_count": int
- "improvement_signal": {{"signal_type": str, "hint": str, "confidence": float}}

Return ONLY valid JSON. No markdown fences."""
        response = await self._provider.complete([{"role": "user", "content": prompt}])
        return _parse_merge(response, existing_records, new_records)


def _parse_merge(
    response: dict,
    existing: list[dict],
    new_records: list[dict],
) -> dict:
    result = {
        "merged_records": existing + new_records,
        "added_count": len(new_records),
        "updated_count": 0,
        "improvement_signal": ImprovementSignal(
            signal_type="merge", prompt_source="prompt4"
        ),
        "cost_usd": response.get("cost_usd", 0.0),
        "error": response.get("error"),
    }
    if response.get("error"):
        return result
    try:
        data = json.loads(response["content"])
        result["merged_records"] = data.get("merged_records", existing + new_records)
        result["added_count"] = int(data.get("added_count", len(new_records)))
        result["updated_count"] = int(data.get("updated_count", 0))
        sig_data = data.get("improvement_signal", {})
        result["improvement_signal"] = ImprovementSignal(
            signal_type=sig_data.get("signal_type", "merge"),
            hint=sig_data.get("hint", ""),
            confidence=float(sig_data.get("confidence", 0.5)),
            prompt_source="prompt4",
        )
    except Exception:  # noqa: BLE001
        pass
    return result
