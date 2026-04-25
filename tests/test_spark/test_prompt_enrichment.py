"""Confirm CrawlInput.metadata + Skill.negative_keywords reach every prompt
that's supposed to receive them. Each test patches LLMProvider.complete so we
can introspect the rendered prompt that would have been sent."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from jugnu.contracts import FetchResult
from jugnu.spark.consolidator import MemoryConsolidator
from jugnu.spark.discovery_llm import DiscoveryLLM
from jugnu.spark.external_ranker_llm import ExternalRankerLLM
from jugnu.spark.extraction_llm import ExtractionLLM
from jugnu.spark.input_metadata import (
    render_input_metadata,
    render_negative_keywords,
)
from jugnu.spark.merge_llm import MergeLLM
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory
from jugnu.spark.warmup import WarmupOrchestrator


METADATA = {"property_name": "San Artes", "city": "Scottsdale", "expected_total_units": 46}
NEGATIVE_KEYWORDS = ["MODULE_", "Lease Magnet"]


def test_render_input_metadata_empty():
    assert render_input_metadata(None) == "(none provided)"
    assert render_input_metadata({}) == "(none provided)"


def test_render_input_metadata_dumps_sorted_json():
    out = render_input_metadata({"b": 2, "a": 1})
    assert '"a": 1' in out
    assert '"b": 2' in out


def test_render_negative_keywords_empty():
    assert render_negative_keywords(None) == "(none)"
    assert render_negative_keywords([]) == "(none)"


def test_render_negative_keywords_joins():
    assert render_negative_keywords(["a", "b"]) == "a, b"


async def _capture_prompt(call):
    """Patch provider.complete to capture the prompt we would have sent."""
    captured = {}

    async def _fake(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        captured["kwargs"] = kwargs
        return {"content": "{}", "cost_usd": 0.0, "error": None}

    provider = LLMProvider()
    with patch.object(provider, "complete", new=AsyncMock(side_effect=_fake)):
        await call(provider)
    return captured["prompt"]


@pytest.mark.asyncio
async def test_extraction_prompt_carries_metadata_and_negatives():
    fetch_result = FetchResult(url="https://x.example", html="<html></html>")

    async def _call(provider):
        await ExtractionLLM(provider).extract(
            fetch_result=fetch_result,
            fields=["proj_name", "units"],
            input_metadata=METADATA,
            negative_keywords=NEGATIVE_KEYWORDS,
        )

    prompt = await _capture_prompt(_call)
    assert "San Artes" in prompt
    assert "Scottsdale" in prompt
    assert "MODULE_" in prompt
    assert "Lease Magnet" in prompt


@pytest.mark.asyncio
async def test_discovery_prompt_carries_url_specific_noise():
    fetch_result = FetchResult(url="https://x.example", html="<html></html>")

    async def _call(provider):
        await DiscoveryLLM(provider).discover(
            fetch_result=fetch_result,
            general_instructions="extract property",
            output_fields=["proj_name", "units"],
            minimum_fields=["proj_name"],
            input_metadata=METADATA,
            negative_keywords=NEGATIVE_KEYWORDS,
            url_specific_noise=["/api/v1/promotions"],
        )

    prompt = await _capture_prompt(_call)
    assert "San Artes" in prompt
    assert "MODULE_" in prompt
    assert "/api/v1/promotions" in prompt


@pytest.mark.asyncio
async def test_merge_prompt_carries_metadata_and_negatives():
    async def _call(provider):
        await MergeLLM(provider).merge(
            existing_records=[{"website": "https://x"}],
            new_records=[{"website": "https://x"}],
            primary_key="website",
            merging_keys=["website"],
            input_metadata=METADATA,
            negative_keywords=NEGATIVE_KEYWORDS,
        )

    prompt = await _capture_prompt(_call)
    assert "San Artes" in prompt
    assert "MODULE_" in prompt


@pytest.mark.asyncio
async def test_external_rank_prompt_carries_metadata_and_negatives():
    async def _call(provider):
        await ExternalRankerLLM(provider).rank_external(
            general_instructions="extract",
            output_fields=["proj_name"],
            missing_fields=["proj_name"],
            extracted_records=[],
            external_links=[{"url": "https://other.example", "score": 0.5}],
            current_depth=0,
            max_depth=1,
            input_metadata=METADATA,
            negative_keywords=NEGATIVE_KEYWORDS,
        )

    prompt = await _capture_prompt(_call)
    assert "San Artes" in prompt
    assert "MODULE_" in prompt


@pytest.mark.asyncio
async def test_warmup_seeds_negative_keywords_into_noise_floor():
    response_data: dict = {"known_noise_patterns": ["/already-known"]}

    provider = LLMProvider()
    with patch.object(
        provider,
        "complete",
        new=AsyncMock(
            return_value={"content": json.dumps(response_data), "cost_usd": 0.0, "error": None}
        ),
    ):
        memory = await WarmupOrchestrator(provider).warm_up(
            skill_name="t",
            skill_version="1.0.0",
            skill_description="",
            output_fields=["x"],
            source_hints=[],
            negative_keywords=["MODULE_", "Lease Magnet"],
        )
    assert "/already-known" in memory.known_noise_patterns
    assert "MODULE_" in memory.known_noise_patterns
    assert "Lease Magnet" in memory.known_noise_patterns


@pytest.mark.asyncio
async def test_consolidator_re_adds_negative_keywords_after_apply():
    """Even if Prompt-6 drops a caller-supplied keyword, the floor restores it."""
    memory = SkillMemory.create_for_skill("t", "1.0.0")
    memory.add_signal(ImprovementSignal(signal_type="extraction"))

    response_data = {
        "high_confidence_api_patterns": [],
        "high_confidence_link_keywords": [],
        "field_extraction_hints": {},
        "platform_fingerprints": {},
        "navigation_wisdom": "",
        "confirmed_field_synonyms": {},
        "known_noise_patterns": [],  # consolidator drops them
        "prompt1_context": "",
        "prompt2_context": "",
        "prompt4_context": "",
        "summary": "",
    }
    provider = LLMProvider()
    with patch.object(
        provider,
        "complete",
        new=AsyncMock(
            return_value={"content": json.dumps(response_data), "cost_usd": 0.0, "error": None}
        ),
    ):
        updated = await MemoryConsolidator(provider).consolidate(
            memory,
            triggered_by="batch",
            negative_keywords=["MODULE_"],
        )
    assert "MODULE_" in updated.known_noise_patterns
