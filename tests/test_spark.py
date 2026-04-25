from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from jugnu.contracts import FetchResult
from jugnu.spark.content_cleaner import html_to_fit_markdown, strip_html_tags
from jugnu.spark.consolidator import MemoryConsolidator
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import ImprovementSignal, SkillMemory
from jugnu.spark.warmup import WarmupOrchestrator


SAMPLE_HTML = """
<html>
<head><style>.nav { display: none; }</style></head>
<body>
<nav>Navigation</nav>
<h1>Product Title</h1>
<p>Price: $29.99</p>
<footer>Footer content</footer>
</body>
</html>
"""


def test_html_to_fit_markdown_removes_noise():
    md = html_to_fit_markdown(SAMPLE_HTML)
    assert "Product Title" in md
    # nav/footer should be stripped
    assert len(md) < len(SAMPLE_HTML)


def test_html_to_fit_markdown_truncates():
    long_html = "<p>" + "a" * 20000 + "</p>"
    md = html_to_fit_markdown(long_html, max_chars=100)
    assert len(md) <= 120  # some extra for truncation marker
    assert "truncated" in md


def test_html_to_fit_markdown_never_raises():
    for bad in ["", "not html", "<<<<invalid>>>", None]:  # type: ignore[list-item]
        result = html_to_fit_markdown(bad or "")
        assert isinstance(result, str)


def test_strip_html_tags():
    assert "Hello" in strip_html_tags("<b>Hello</b> <i>World</i>")
    assert "World" in strip_html_tags("<b>Hello</b> <i>World</i>")


async def test_warmup_returns_skill_memory():
    provider = LLMProvider()
    response_data = {
        "api_patterns": ["/api/v1/"],
        "link_keywords": ["items", "catalog"],
        "field_hints": {"title": "Look for h1 or .product-title"},
        "navigation_wisdom": "Scroll to load more",
        "platform_fingerprints": {"shopify": ["cdn.shopify.com"]},
    }
    with patch.object(
        provider,
        "complete",
        new=AsyncMock(return_value={"content": json.dumps(response_data), "cost_usd": 0.001, "error": None}),
    ):
        warmup = WarmupOrchestrator(provider)
        memory = await warmup.warm_up(
            skill_name="test",
            skill_version="1.0.0",
            skill_description="Test crawler",
            output_fields=["title", "price"],
            source_hints=[],
        )
    assert isinstance(memory, SkillMemory)
    assert "/api/v1/" in memory.high_confidence_api_patterns
    assert memory.warmup_cost_usd == 0.001


async def test_warmup_returns_existing_fresh_memory():
    """Warm-up should return existing memory if it's fresh (not stale)."""
    from jugnu.skill import OutputSchema, Skill  # noqa: PLC0415

    existing = SkillMemory.create_for_skill("my_skill", "1.0.0")
    existing.high_confidence_api_patterns = ["/existing/"]

    class _Proxy:
        name = "my_skill"
        version = "1.0.0"

    provider = LLMProvider()
    warmup = WarmupOrchestrator(provider)
    result = await warmup.warm_up(
        skill_name="my_skill",
        skill_version="1.0.0",
        skill_description="",
        output_fields=[],
        source_hints=[],
        existing_memory=existing,
    )
    assert result is existing


async def test_consolidator_clears_pending_signals():
    provider = LLMProvider()
    memory = SkillMemory.create_for_skill("test", "1.0.0")
    memory.add_signal(ImprovementSignal(signal_type="api_pattern", hint="/api/v2/"))
    memory.add_signal(ImprovementSignal(signal_type="dom_selector", hint=".item-card"))

    consolidation_result = {
        "high_confidence_api_patterns": ["/api/v2/"],
        "high_confidence_link_keywords": [],
        "field_extraction_hints": {},
        "platform_fingerprints": {},
        "navigation_wisdom": "",
        "confirmed_field_synonyms": {},
        "known_noise_patterns": [],
        "prompt1_context": "",
        "prompt2_context": "",
        "prompt4_context": "",
        "summary": "Added API pattern",
    }
    with patch.object(
        provider,
        "complete",
        new=AsyncMock(
            return_value={"content": json.dumps(consolidation_result), "cost_usd": 0.002, "error": None}
        ),
    ):
        consolidator = MemoryConsolidator(provider)
        updated = await consolidator.consolidate(memory, triggered_by="batch")

    assert updated.pending_signal_count() == 0
    assert updated.memory_version == 2
    assert len(updated.consolidation_log) == 1
    assert updated.consolidation_log[0].triggered_by == "batch"


def test_consolidator_should_trigger_batch():
    provider = LLMProvider()
    consolidator = MemoryConsolidator(provider)
    memory = SkillMemory.create_for_skill("test", "1.0.0")
    for i in range(50):
        memory.add_signal(ImprovementSignal(signal_type="test"))
    assert consolidator.should_consolidate_batch(memory, batch_size=50) is True


def test_consolidator_should_trigger_smart():
    provider = LLMProvider()
    consolidator = MemoryConsolidator(provider)
    memory = SkillMemory.create_for_skill("test", "1.0.0")
    assert consolidator.should_consolidate_smart(memory, new_platform_confirmations=3, trigger_count=3) is True
    assert consolidator.should_consolidate_smart(memory, new_platform_confirmations=2, trigger_count=3) is False
