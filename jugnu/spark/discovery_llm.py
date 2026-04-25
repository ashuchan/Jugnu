from __future__ import annotations

import json

from jugnu.contracts import FetchResult
from jugnu.spark.content_cleaner import html_to_fit_markdown
from jugnu.spark.prompts import render_template
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory


class DiscoveryLLM:
    """Prompt-1: Rank links and APIs given a fetched page.

    Inputs to the LLM (per spec):
      - skill_memory.prompt1_context (injected verbatim)
      - skill.general_instructions (extraction goal)
      - skill.output_schema.fields and minimum_fields
      - skill_memory.known_noise_patterns
      - captured API candidates and internal hyperlinks
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def discover(
        self,
        fetch_result: FetchResult,
        general_instructions: str,
        output_fields: list[str],
        minimum_fields: list[str],
        api_candidates: list[dict] | list[str] | None = None,
        link_candidates: list[dict] | list[str] | None = None,
        memory: SkillMemory | None = None,
        skill_name: str = "",
    ) -> dict:
        fit_md = html_to_fit_markdown(fetch_result.html)
        prompt1_context = (memory.prompt1_context if memory else "") or "(no prior domain memory)"
        noise = (memory.known_noise_patterns if memory else []) or []

        prompt = render_template(
            "discovery",
            url=fetch_result.url,
            content_type=fetch_result.content_type or "(unknown)",
            fit_markdown=fit_md,
            prompt1_context=prompt1_context,
            general_instructions=general_instructions or "(none)",
            output_fields=", ".join(output_fields) or "(none)",
            minimum_fields=", ".join(minimum_fields) or "(none)",
            api_candidates_json=json.dumps(api_candidates or [], indent=2, default=str),
            link_candidates_json=json.dumps(link_candidates or [], indent=2, default=str),
            known_noise_patterns=", ".join(noise) or "(none)",
        )
        response = await self._provider.complete(
            [{"role": "user", "content": prompt}],
            stage="prompt1_discovery",
            url=fetch_result.url,
            skill=skill_name,
        )
        return _parse_discovery(response, fetch_result.url)


def _parse_discovery(response: dict, url: str) -> dict:
    cost = float(response.get("cost_usd") or 0.0)
    result = {
        "ranked_apis": [],
        "ranked_links": [],
        "platform_guess": None,
        "navigation_hint": "",
        "improvement_signal": ImprovementSignal(
            signal_type="discovery", url=url, prompt_source="prompt1"
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
    result["ranked_apis"] = data.get("ranked_apis") or []
    result["ranked_links"] = data.get("ranked_links") or []
    result["platform_guess"] = data.get("platform_guess")
    result["navigation_hint"] = data.get("navigation_hint", "")

    sig = data.get("improvement_signal") or {}
    platform_observed = sig.get("platform_observed") or data.get("platform_guess")
    free_text = sig.get("free_text_observation", "")
    misleading = sig.get("misleading_patterns") or []
    result["improvement_signal"] = ImprovementSignal(
        signal_type="discovery",
        url=url,
        platform=platform_observed,
        hint=free_text or (misleading[0] if misleading else ""),
        confidence=float(sig.get("confidence", 0.5)),
        prompt_source="prompt1",
        raw_context=json.dumps(sig, default=str),
    )
    return result
