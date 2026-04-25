from __future__ import annotations

import json

from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import SkillMemory


class WarmupOrchestrator:
    """Runs Prompt-5 once at session start — never fetches a URL."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def warm_up(
        self,
        skill_name: str,
        skill_version: str,
        skill_description: str,
        output_fields: list[str],
        source_hints: list[dict],
        existing_memory: SkillMemory | None = None,
    ) -> SkillMemory:
        if existing_memory and not existing_memory.is_stale_for(
            _SkillProxy(skill_name, skill_version)
        ):
            return existing_memory

        prompt = _build_warmup_prompt(
            skill_name=skill_name,
            description=skill_description,
            fields=output_fields,
            hints=source_hints,
        )
        response = await self._provider.complete(
            [{"role": "user", "content": prompt}]
        )
        memory = SkillMemory.create_for_skill(skill_name, skill_version)
        memory.warmup_cost_usd = response.get("cost_usd", 0.0)
        if not response.get("error"):
            _apply_warmup_response(memory, response["content"])
        return memory


def _build_warmup_prompt(
    skill_name: str,
    description: str,
    fields: list[str],
    hints: list[dict],
) -> str:
    return f"""You are an expert web data extraction assistant.

Skill: {skill_name}
Description: {description}
Target fields: {', '.join(fields)}
Source hints: {json.dumps(hints, indent=2)}

Without fetching any URL, generate a JSON object with:
- "api_patterns": list[str] — likely API URL patterns for this domain type
- "link_keywords": list[str] — URL keywords likely to lead to target records
- "field_hints": dict[str, str] — extraction hints per field
- "navigation_wisdom": str — general navigation advice
- "platform_fingerprints": dict[str, list[str]] — known platform signals

Return ONLY valid JSON. No markdown fences."""


def _apply_warmup_response(memory: SkillMemory, content: str) -> None:
    try:
        data = json.loads(content)
        memory.high_confidence_api_patterns = data.get("api_patterns", [])
        memory.high_confidence_link_keywords = data.get("link_keywords", [])
        memory.field_extraction_hints = data.get("field_hints", {})
        memory.navigation_wisdom = data.get("navigation_wisdom", "")
        memory.platform_fingerprints = data.get("platform_fingerprints", {})
    except Exception:  # noqa: BLE001
        pass


class _SkillProxy:
    def __init__(self, name: str, version: str) -> None:
        self.name = name
        self.version = version
