from __future__ import annotations

import json

from jugnu.contracts import FetchResult
from jugnu.spark.content_cleaner import html_to_fit_markdown
from jugnu.spark.prompts import render_template
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory


class ExtractionLLM:
    """Prompt-2: Extract structured records from a page. Never sends raw HTML.

    Inputs to the LLM (per spec):
      - skill_memory.prompt2_context (injected verbatim)
      - skill.general_instructions
      - skill.output_schema (fields, minimum_fields, json_schema)
      - skill_memory.confirmed_field_synonyms
      - skill_memory.field_extraction_hints
      - the source URL, content type, and fit_markdown content
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def extract(
        self,
        fetch_result: FetchResult,
        fields: list[str],
        minimum_fields: list[str] | None = None,
        output_schema: dict | None = None,
        memory: SkillMemory | None = None,
        general_instructions: str = "",
        custom_instructions: str = "",
        skill_name: str = "",
    ) -> dict:
        fit_md = html_to_fit_markdown(fetch_result.html)
        prompt2_context = (memory.prompt2_context if memory else "") or "(no prior domain memory)"
        synonyms = (memory.confirmed_field_synonyms if memory else {}) or {}
        field_hints = (memory.field_extraction_hints if memory else {}) or {}
        # Restrict synonyms / hints to the fields actually in the output schema.
        synonyms_filtered = {k: v for k, v in synonyms.items() if k in fields}
        hints_filtered = {k: v for k, v in field_hints.items() if k in fields}

        prompt = render_template(
            "extraction",
            url=fetch_result.url,
            content_type=fetch_result.content_type or "(unknown)",
            fit_markdown=fit_md,
            prompt2_context=prompt2_context,
            general_instructions=general_instructions or "(none)",
            output_fields=", ".join(fields) or "(none)",
            output_schema_json=json.dumps(
                output_schema or {"fields": fields}, indent=2, default=str
            ),
            minimum_fields=", ".join(minimum_fields or []) or "(none)",
            confirmed_field_synonyms_json=json.dumps(synonyms_filtered, indent=2, default=str),
            field_extraction_hints_json=json.dumps(hints_filtered, indent=2, default=str),
            custom_instructions=custom_instructions or "(none)",
        )
        response = await self._provider.complete(
            [{"role": "user", "content": prompt}],
            stage="prompt2_extraction",
            url=fetch_result.url,
            skill=skill_name,
        )
        return _parse_extraction(response, fetch_result.url)


def _parse_extraction(response: dict, url: str) -> dict:
    cost = float(response.get("cost_usd") or 0.0)
    result = {
        "records": [],
        "confidence": 0.0,
        "platform": None,
        "field_mappings": {},
        "field_mapping_notes": "",
        "improvement_signal": ImprovementSignal(
            signal_type="extraction", url=url, prompt_source="prompt2"
        ),
        "cost_usd": cost,
        "error": response.get("error"),
    }
    if response.get("error"):
        return result
    try:
        data = json.loads(response.get("content") or "")
    except json.JSONDecodeError:
        result["error"] = "invalid_json"
        return result

    records = data.get("records") or []
    result["records"] = records
    result["platform"] = data.get("platform_confirmed") or data.get("platform")
    result["field_mappings"] = data.get("field_mappings") or {}
    result["field_mapping_notes"] = data.get("field_mapping_notes", "")

    confidences = [float(r.get("confidence", 0.0)) for r in records if isinstance(r, dict)]
    if confidences:
        result["confidence"] = sum(confidences) / len(confidences)
    elif "confidence" in data:
        result["confidence"] = float(data.get("confidence") or 0.0)

    sig = data.get("improvement_signal") or {}
    synonyms = sig.get("field_synonyms_discovered") or {}
    first_field = next(iter(synonyms), "") if synonyms else ""
    api_worked = sig.get("api_patterns_that_worked") or []
    hint = ""
    if api_worked:
        hint = api_worked[0]
    elif first_field and synonyms.get(first_field):
        hint = synonyms[first_field][0]
    result["improvement_signal"] = ImprovementSignal(
        signal_type="extraction",
        url=url,
        field_name=first_field,
        hint=hint or sig.get("free_text_observation", ""),
        platform=result["platform"],
        confidence=float(sig.get("confidence", result["confidence"] or 0.5)),
        prompt_source="prompt2",
        raw_context=json.dumps(sig, default=str),
    )
    return result
