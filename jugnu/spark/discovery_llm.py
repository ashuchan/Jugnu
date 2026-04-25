from __future__ import annotations

import json
from typing import Optional

from jugnu.contracts import FetchResult
from jugnu.spark.content_cleaner import html_to_fit_markdown
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory


class DiscoveryLLM:
    """Prompt-1: Discover and rank links given a fetched page."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def discover(
        self,
        fetch_result: FetchResult,
        target_description: str,
        memory: Optional[SkillMemory] = None,
    ) -> dict:
        fit_md = html_to_fit_markdown(fetch_result.html)
        memory_ctx = _memory_context(memory, "prompt1")
        prompt = f"""You are a web crawler discovery assistant.

URL: {fetch_result.url}
Page content (fit markdown):
{fit_md}

Memory context:
{memory_ctx}

Task: Analyze this page and identify the best links/endpoints to crawl next to find {target_description}.

Return a JSON object with:
- "ranked_links": list of {{"url": str, "score": float, "reason": str}}
- "detected_platform": str or null
- "api_endpoints": list[str]
- "improvement_signal": {{"signal_type": str, "hint": str, "confidence": float}}

Return ONLY valid JSON. No markdown fences."""
        response = await self._provider.complete([{"role": "user", "content": prompt}])
        return _parse_discovery(response, fetch_result.url)


def _parse_discovery(response: dict, url: str) -> dict:
    result = {
        "ranked_links": [],
        "detected_platform": None,
        "api_endpoints": [],
        "improvement_signal": ImprovementSignal(
            signal_type="discovery", url=url, prompt_source="prompt1"
        ),
        "cost_usd": response.get("cost_usd", 0.0),
        "error": response.get("error"),
    }
    if response.get("error"):
        return result
    try:
        data = json.loads(response["content"])
        result["ranked_links"] = data.get("ranked_links", [])
        result["detected_platform"] = data.get("detected_platform")
        result["api_endpoints"] = data.get("api_endpoints", [])
        sig_data = data.get("improvement_signal", {})
        result["improvement_signal"] = ImprovementSignal(
            signal_type=sig_data.get("signal_type", "discovery"),
            url=url,
            hint=sig_data.get("hint", ""),
            confidence=float(sig_data.get("confidence", 0.5)),
            prompt_source="prompt1",
        )
    except Exception:  # noqa: BLE001
        pass
    return result


def _memory_context(memory: Optional[SkillMemory], prompt_key: str) -> str:
    if memory is None:
        return ""
    ctx = getattr(memory, f"{prompt_key}_context", "")
    return ctx or ""
