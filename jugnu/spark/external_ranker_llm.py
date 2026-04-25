from __future__ import annotations

import json

from jugnu.spark.input_metadata import render_input_metadata, render_negative_keywords
from jugnu.spark.prompts import render_template
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory


class ExternalRankerLLM:
    """Prompt-4: Last-resort ranking of external links when internal sources fail.

    Inputs to the LLM (per spec):
      - skill_memory.prompt4_context (injected verbatim)
      - skill.general_instructions
      - skill.output_schema.fields
      - missing_fields (which minimum fields are still unfilled)
      - extracted_summary (summary of records already pulled)
      - skill_memory.known_noise_patterns
      - external link candidates with current depth and max depth
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def rank_external(
        self,
        general_instructions: str,
        output_fields: list[str],
        missing_fields: list[str],
        extracted_records: list[dict],
        external_links: list[dict] | list[str],
        current_depth: int,
        max_depth: int,
        memory: SkillMemory | None = None,
        url: str = "",
        skill_name: str = "",
        input_metadata: dict | None = None,
        negative_keywords: list[str] | None = None,
    ) -> dict:
        if max_depth <= 0 or not external_links or not missing_fields:
            return {
                "ranked_external_links": [],
                "improvement_signal": None,
                "cost_usd": 0.0,
                "error": None,
            }

        prompt4_context = (memory.prompt4_context if memory else "") or "(no prior domain memory)"
        noise = (memory.known_noise_patterns if memory else []) or []
        extracted_summary = _summarise_records(extracted_records)

        prompt = render_template(
            "external_rank",
            prompt4_context=prompt4_context,
            general_instructions=general_instructions or "(none)",
            output_fields=", ".join(output_fields) or "(none)",
            missing_fields=", ".join(missing_fields) or "(none)",
            extracted_summary=extracted_summary,
            current_depth=current_depth,
            max_depth=max_depth,
            known_noise_patterns=", ".join(noise) or "(none)",
            external_links_json=json.dumps(external_links, indent=2, default=str),
            input_metadata=render_input_metadata(input_metadata),
            negative_keywords=render_negative_keywords(negative_keywords),
        )
        response = await self._provider.complete(
            [{"role": "user", "content": prompt}],
            stage="prompt4_external_rank",
            url=url,
            skill=skill_name,
        )
        return _parse(response, url)


def _summarise_records(records: list[dict]) -> str:
    if not records:
        return "(no records extracted yet)"
    sample = records[:3]
    return json.dumps(
        {"count": len(records), "sample": sample},
        indent=2,
        default=str,
    )


def _parse(response: dict, url: str) -> dict:
    cost = float(response.get("cost_usd") or 0.0)
    result = {
        "ranked_external_links": [],
        "improvement_signal": ImprovementSignal(
            signal_type="external_rank",
            url=url,
            prompt_source="prompt4",
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

    result["ranked_external_links"] = data.get("ranked_external_links") or []
    sig = data.get("improvement_signal") or {}
    misleading = sig.get("misleading_patterns") or []
    result["improvement_signal"] = ImprovementSignal(
        signal_type="external_rank",
        url=url,
        hint=(misleading[0] if misleading else sig.get("free_text_observation", "")),
        confidence=float(sig.get("confidence", 0.5)),
        prompt_source="prompt4",
        raw_context=json.dumps(sig, default=str),
    )
    return result
