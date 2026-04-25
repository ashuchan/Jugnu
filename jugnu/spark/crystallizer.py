from __future__ import annotations

import json
from typing import Optional

from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory


class ExternalRankerLLM:
    """Prompt-3: Rank external candidate URLs for relevance."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def rank(
        self,
        candidate_urls: list[str],
        target_description: str,
        memory: Optional[SkillMemory] = None,
    ) -> dict:
        memory_ctx = ""
        if memory:
            memory_ctx = memory.prompt1_context or ""
        prompt = f"""You are a link relevance ranking assistant.

Target description: {target_description}
Candidate URLs:
{json.dumps(candidate_urls, indent=2)}

Memory context: {memory_ctx}

Task: Rank these URLs by likelihood of containing {target_description} data.

Return a JSON object with:
- "ranked": list of {{"url": str, "score": float, "reason": str}}
- "skip_urls": list[str]

Return ONLY valid JSON. No markdown fences."""
        response = await self._provider.complete([{"role": "user", "content": prompt}])
        return _parse_rank(response, candidate_urls)


def _parse_rank(response: dict, candidates: list[str]) -> dict:
    result = {
        "ranked": [{"url": u, "score": 0.5, "reason": ""} for u in candidates],
        "skip_urls": [],
        "cost_usd": response.get("cost_usd", 0.0),
        "error": response.get("error"),
    }
    if response.get("error"):
        return result
    try:
        data = json.loads(response["content"])
        result["ranked"] = data.get("ranked", result["ranked"])
        result["skip_urls"] = data.get("skip_urls", [])
    except Exception:  # noqa: BLE001
        pass
    return result
