from __future__ import annotations

import json

from jugnu.spark.input_metadata import render_negative_keywords
from jugnu.spark.prompts import render_template
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import SkillMemory


class WarmupOrchestrator:
    """Runs Prompt-5 once at session start — never fetches a URL.

    Produces a SkillMemory v1 populated with high_confidence_api_patterns,
    high_confidence_link_keywords, field_extraction_hints, platform_fingerprints,
    navigation_wisdom, confirmed_field_synonyms, known_noise_patterns, and the
    three context fragments (prompt1_context, prompt2_context, prompt4_context)
    that downstream prompts inject verbatim.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def warm_up(
        self,
        skill_name: str,
        skill_version: str,
        skill_description: str,
        output_fields: list[str],
        source_hints: list[dict],
        minimum_fields: list[str] | None = None,
        general_instructions: str = "",
        existing_memory: SkillMemory | None = None,
        negative_keywords: list[str] | None = None,
    ) -> SkillMemory:
        if existing_memory and not existing_memory.is_stale_for(
            _SkillProxy(skill_name, skill_version)
        ):
            return existing_memory

        prompt = render_template(
            "warmup",
            skill_name=skill_name,
            skill_version=skill_version,
            skill_description=skill_description or "(no description)",
            general_instructions=general_instructions or "(no general_instructions provided)",
            output_fields=", ".join(output_fields) if output_fields else "(none)",
            minimum_fields=", ".join(minimum_fields or []) or "(none)",
            source_hints_json=json.dumps(source_hints or [], indent=2),
            negative_keywords=render_negative_keywords(negative_keywords),
        )
        response = await self._provider.complete(
            [{"role": "user", "content": prompt}],
            stage="prompt5_warmup",
            skill=skill_name,
        )
        memory = SkillMemory.create_for_skill(skill_name, skill_version)
        memory.warmup_cost_usd = float(response.get("cost_usd") or 0.0)
        if not response.get("error"):
            _apply_warmup_response(memory, response.get("content", ""))
        # Always honor caller-supplied negative_keywords as a noise floor.
        for kw in negative_keywords or []:
            if kw and kw not in memory.known_noise_patterns:
                memory.known_noise_patterns.append(kw)
        return memory


def _apply_warmup_response(memory: SkillMemory, content: str) -> None:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(data, dict):
        return
    memory.high_confidence_api_patterns = list(
        data.get("high_confidence_api_patterns") or data.get("api_patterns") or []
    )
    memory.high_confidence_link_keywords = list(
        data.get("high_confidence_link_keywords") or data.get("link_keywords") or []
    )
    memory.field_extraction_hints = dict(
        data.get("field_extraction_hints") or data.get("field_hints") or {}
    )
    memory.platform_fingerprints = {
        k: list(v) for k, v in (data.get("platform_fingerprints") or {}).items()
    }
    memory.navigation_wisdom = str(data.get("navigation_wisdom") or "")
    memory.confirmed_field_synonyms = {
        k: list(v) for k, v in (data.get("confirmed_field_synonyms") or {}).items()
    }
    memory.known_noise_patterns = list(data.get("known_noise_patterns") or [])
    memory.prompt1_context = str(data.get("prompt1_context") or "")
    memory.prompt2_context = str(data.get("prompt2_context") or "")
    memory.prompt4_context = str(data.get("prompt4_context") or "")


class _SkillProxy:
    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version
