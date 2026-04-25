from __future__ import annotations

import json

from jugnu.contracts import FetchResult
from jugnu.spark.content_cleaner import html_to_fit_markdown
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory


class ExtractionLLM:
    """Prompt-2: Extract structured records from a page. Never sends raw HTML."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def extract(
        self,
        fetch_result: FetchResult,
        fields: list[str],
        memory: SkillMemory | None = None,
        custom_instructions: str = "",
    ) -> dict:
        fit_md = html_to_fit_markdown(fetch_result.html)
        memory_ctx = ""
        if memory:
            memory_ctx = memory.prompt2_context or ""
            for field, hint in memory.field_extraction_hints.items():
                if field in fields:
                    memory_ctx += f"\n{field}: {hint}"
        instructions = f"\nExtra instructions: {custom_instructions}" if custom_instructions else ""
        prompt = f"""You are a structured data extraction assistant.

URL: {fetch_result.url}
Target fields: {', '.join(fields)}
Page content (fit markdown):
{fit_md}

Memory context:
{memory_ctx}{instructions}

Task: Extract all records matching the target fields from the page content.

Return a JSON object with:
- "records": list[dict] - extracted records
- "confidence": float - 0.0 to 1.0
- "platform": str or null
- "improvement_signal": {{"signal_type": str, "field_name": str, "hint": str, "confidence": float}}

Return ONLY valid JSON. No markdown fences."""
        response = await self._provider.complete([{"role": "user", "content": prompt}])
        return _parse_extraction(response, fetch_result.url)


def _parse_extraction(response: dict, url: str) -> dict:
    result = {
        "records": [],
        "confidence": 0.0,
        "platform": None,
        "improvement_signal": ImprovementSignal(
            signal_type="extraction", url=url, prompt_source="prompt2"
        ),
        "cost_usd": response.get("cost_usd", 0.0),
        "error": response.get("error"),
    }
    if response.get("error"):
        return result
    try:
        data = json.loads(response["content"])
        result["records"] = data.get("records", [])
        result["confidence"] = float(data.get("confidence", 0.0))
        result["platform"] = data.get("platform")
        sig_data = data.get("improvement_signal", {})
        result["improvement_signal"] = ImprovementSignal(
            signal_type=sig_data.get("signal_type", "extraction"),
            url=url,
            field_name=sig_data.get("field_name", ""),
            hint=sig_data.get("hint", ""),
            confidence=float(sig_data.get("confidence", 0.5)),
            prompt_source="prompt2",
        )
    except Exception:  # noqa: BLE001
        pass
    return result
