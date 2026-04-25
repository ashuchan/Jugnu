"""Tests for the cross-phase wiring fixes:
- Warmup template now requests + parses prompt1/2/4 contexts.
- Discovery / Extraction / External / Merge LLMs receive schema + instructions + hints.
- Crawler wires Prompt-3 (merge) and Prompt-4 (external rank).
- MemoryConsolidator smart trigger counts new platforms in pending_signals.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from jugnu.contracts import FetchResult
from jugnu.spark.consolidator import MemoryConsolidator
from jugnu.spark.discovery_llm import DiscoveryLLM
from jugnu.spark.external_ranker_llm import ExternalRankerLLM
from jugnu.spark.extraction_llm import ExtractionLLM
from jugnu.spark.merge_llm import MergeLLM
from jugnu.spark.prompts import render_template
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory
from jugnu.spark.warmup import WarmupOrchestrator


def test_warmup_template_includes_context_fragment_outputs():
    rendered = render_template(
        "warmup",
        skill_name="x",
        skill_version="1.0",
        skill_description="desc",
        general_instructions="grab apartments",
        output_fields="rent, beds",
        minimum_fields="rent",
        source_hints_json="[]",
    )
    # Spec fields appear in the output schema description that the LLM must produce:
    assert "prompt1_context" in rendered
    assert "prompt2_context" in rendered
    assert "prompt4_context" in rendered
    # general_instructions placeholder was substituted with the supplied text:
    assert "grab apartments" in rendered
    # output schema fields and minimum_fields were substituted in:
    assert "rent, beds" in rendered
    assert "Minimum required fields: rent" in rendered


async def test_warmup_parses_all_context_fragments():
    provider = LLMProvider()
    response_data = {
        "high_confidence_api_patterns": ["/api/v1/listings"],
        "high_confidence_link_keywords": ["floor-plans"],
        "field_extraction_hints": {"rent": "Look for monthlyRent"},
        "platform_fingerprints": {"rentcafe": ["/api/getApartments"]},
        "navigation_wisdom": "watch xhr",
        "confirmed_field_synonyms": {"rent": ["monthlyRent", "rentAmount"]},
        "known_noise_patterns": ["/api/chat"],
        "prompt1_context": "discovery wisdom paragraph",
        "prompt2_context": "extraction wisdom paragraph",
        "prompt4_context": "external rank wisdom paragraph",
    }
    with patch.object(
        provider,
        "complete",
        new=AsyncMock(
            return_value={"content": json.dumps(response_data), "cost_usd": 0.001, "error": None}
        ),
    ):
        warmup = WarmupOrchestrator(provider)
        memory = await warmup.warm_up(
            skill_name="real_estate",
            skill_version="1.0",
            skill_description="apartments",
            output_fields=["rent", "beds"],
            minimum_fields=["rent"],
            general_instructions="extract apartment rent and beds",
            source_hints=[{"platform": "rentcafe"}],
        )
    assert memory.prompt1_context == "discovery wisdom paragraph"
    assert memory.prompt2_context == "extraction wisdom paragraph"
    assert memory.prompt4_context == "external rank wisdom paragraph"
    assert memory.known_noise_patterns == ["/api/chat"]
    assert memory.confirmed_field_synonyms == {"rent": ["monthlyRent", "rentAmount"]}


async def test_discovery_llm_injects_minimum_fields_and_noise():
    provider = LLMProvider()
    fetched: list[str] = []

    async def fake_complete(messages, **_kw):
        fetched.append(messages[0]["content"])
        return {
            "content": json.dumps(
                {
                    "ranked_apis": [],
                    "ranked_links": [],
                    "platform_guess": None,
                    "navigation_hint": "",
                    "improvement_signal": {"prompt_stage": "discovery"},
                }
            ),
            "cost_usd": 0.0,
            "error": None,
        }

    with patch.object(provider, "complete", new=fake_complete):
        memory = SkillMemory.create_for_skill("s", "1.0")
        memory.prompt1_context = "MEM1_CTX"
        memory.known_noise_patterns = ["/api/chat", "/track"]
        d = DiscoveryLLM(provider)
        await d.discover(
            FetchResult(url="https://x", html="<html></html>", content_type="text/html"),
            general_instructions="EXTRACT_GOAL",
            output_fields=["rent", "beds"],
            minimum_fields=["rent"],
            api_candidates=[{"url": "/api/listings"}],
            link_candidates=[{"href": "/floor-plans"}],
            memory=memory,
        )
    [prompt] = fetched
    assert "MEM1_CTX" in prompt
    assert "EXTRACT_GOAL" in prompt
    assert "rent, beds" in prompt
    assert "Minimum required fields" in prompt
    assert "/api/chat" in prompt
    assert "/api/listings" in prompt


async def test_extraction_llm_injects_schema_and_synonyms():
    provider = LLMProvider()
    fetched: list[str] = []

    async def fake_complete(messages, **_kw):
        fetched.append(messages[0]["content"])
        return {
            "content": json.dumps(
                {
                    "records": [{"rent": 1000, "beds": 1, "confidence": 0.9}],
                    "field_mappings": {"api": {}, "dom": {}},
                    "platform_confirmed": "rentcafe",
                    "improvement_signal": {"prompt_stage": "extraction", "succeeded": True},
                }
            ),
            "cost_usd": 0.0,
            "error": None,
        }

    with patch.object(provider, "complete", new=fake_complete):
        memory = SkillMemory.create_for_skill("s", "1.0")
        memory.prompt2_context = "MEM2_CTX"
        memory.confirmed_field_synonyms = {"rent": ["monthlyRent"], "ignored": ["x"]}
        memory.field_extraction_hints = {"rent": "look for monthlyRent"}
        e = ExtractionLLM(provider)
        result = await e.extract(
            FetchResult(url="https://x", html="<p>$1000</p>", content_type="text/html"),
            fields=["rent", "beds"],
            minimum_fields=["rent"],
            output_schema={"fields": ["rent", "beds"], "minimum_fields": ["rent"]},
            memory=memory,
            general_instructions="EXTRACT_GOAL",
        )
    [prompt] = fetched
    assert "MEM2_CTX" in prompt
    assert "EXTRACT_GOAL" in prompt
    assert "monthlyRent" in prompt  # synonym for in-schema field
    assert "ignored" not in prompt  # filtered out — not in schema fields
    assert result["records"][0]["rent"] == 1000


async def test_merge_llm_uses_general_instructions_not_prompt4_context():
    provider = LLMProvider()
    fetched: list[str] = []

    async def fake_complete(messages, **_kw):
        fetched.append(messages[0]["content"])
        return {
            "content": json.dumps(
                {
                    "merge_decisions": [
                        {
                            "new_record_index": 0,
                            "existing_record_id": "A",
                            "merge": True,
                            "reason": "match",
                        }
                    ]
                }
            ),
            "cost_usd": 0.0,
            "error": None,
        }

    with patch.object(provider, "complete", new=fake_complete):
        memory = SkillMemory.create_for_skill("s", "1.0")
        memory.prompt4_context = "SHOULD_NOT_LEAK"
        m = MergeLLM(provider)
        result = await m.merge(
            existing_records=[{"id": "A", "price": 10}],
            new_records=[{"id": "A", "price": 12}],
            primary_key="id",
            merging_keys=["id"],
            general_instructions="DOMAIN_INSTRUCTIONS",
            memory=memory,
        )
    [prompt] = fetched
    assert "DOMAIN_INSTRUCTIONS" in prompt
    assert "SHOULD_NOT_LEAK" not in prompt  # no leak from wrong context
    assert result["updated_count"] == 1
    # merged record reflects the new price
    assert any(r.get("price") == 12 for r in result["merged_records"])


async def test_merge_llm_short_circuits_on_no_existing():
    provider = LLMProvider()
    with patch.object(provider, "complete", new=AsyncMock()) as m:
        merger = MergeLLM(provider)
        result = await merger.merge(
            existing_records=[],
            new_records=[{"id": "A"}, {"id": "B"}],
            primary_key="id",
            merging_keys=["id"],
        )
        m.assert_not_called()  # no LLM hit when nothing to merge against
    assert result["added_count"] == 2
    assert result["updated_count"] == 0


async def test_external_ranker_llm_skips_when_no_external_links():
    provider = LLMProvider()
    with patch.object(provider, "complete", new=AsyncMock()) as m:
        ranker = ExternalRankerLLM(provider)
        result = await ranker.rank_external(
            general_instructions="g",
            output_fields=["rent"],
            missing_fields=["rent"],
            extracted_records=[],
            external_links=[],
            current_depth=0,
            max_depth=1,
        )
        m.assert_not_called()
    assert result["ranked_external_links"] == []


async def test_external_ranker_llm_invokes_with_full_inputs():
    provider = LLMProvider()
    fetched: list[str] = []

    async def fake_complete(messages, **_kw):
        fetched.append(messages[0]["content"])
        return {
            "content": json.dumps(
                {
                    "ranked_external_links": [
                        {"url": "https://other.com", "confidence": 0.7, "reason": "r", "depth": 1}
                    ],
                    "improvement_signal": {"prompt_stage": "external_rank", "succeeded": False},
                }
            ),
            "cost_usd": 0.0,
            "error": None,
        }

    with patch.object(provider, "complete", new=fake_complete):
        memory = SkillMemory.create_for_skill("s", "1.0")
        memory.prompt4_context = "EXT_CTX"
        memory.known_noise_patterns = ["/ads/"]
        ranker = ExternalRankerLLM(provider)
        result = await ranker.rank_external(
            general_instructions="EXTRACT_GOAL",
            output_fields=["rent"],
            missing_fields=["rent"],
            extracted_records=[{"price": 1}],
            external_links=[{"url": "https://other.com", "score": 0.5}],
            current_depth=0,
            max_depth=2,
            memory=memory,
        )
    [prompt] = fetched
    assert "EXT_CTX" in prompt
    assert "EXTRACT_GOAL" in prompt
    assert "/ads/" in prompt
    assert "rent" in prompt
    assert result["ranked_external_links"][0]["url"] == "https://other.com"


def test_consolidator_count_new_platform_confirmations():
    provider = LLMProvider()
    consolidator = MemoryConsolidator(provider)
    memory = SkillMemory.create_for_skill("s", "1.0")
    memory.platform_fingerprints = {"known_platform": ["/known"]}
    # Three signals reporting a new platform → smart trigger should fire.
    for _ in range(3):
        memory.add_signal(
            ImprovementSignal(signal_type="discovery", platform="new_platform")
        )
    # One known platform — should NOT count toward smart trigger.
    memory.add_signal(
        ImprovementSignal(signal_type="discovery", platform="known_platform")
    )
    count = consolidator.count_new_platform_confirmations(memory)
    assert count == 3
    assert consolidator.should_consolidate_smart(memory, count, trigger_count=3) is True
