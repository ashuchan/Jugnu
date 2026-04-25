from __future__ import annotations

import pytest

from jugnu.skill import OutputSchema, Skill
from jugnu.spark.skill_memory import ConsolidationLogEntry, ImprovementSignal, SkillMemory


def test_compute_hash_deterministic():
    h1 = SkillMemory.compute_hash("my_skill", "1.0.0")
    h2 = SkillMemory.compute_hash("my_skill", "1.0.0")
    assert h1 == h2


def test_compute_hash_length():
    h = SkillMemory.compute_hash("my_skill", "1.0.0")
    assert len(h) == 16


def test_compute_hash_different_for_different_inputs():
    h1 = SkillMemory.compute_hash("skill_a", "1.0.0")
    h2 = SkillMemory.compute_hash("skill_b", "1.0.0")
    assert h1 != h2


def test_create_for_skill():
    mem = SkillMemory.create_for_skill("news_crawler", "2.0.0")
    assert mem.skill_name == "news_crawler"
    assert mem.skill_version == "2.0.0"
    assert mem.skill_hash == SkillMemory.compute_hash("news_crawler", "2.0.0")
    assert mem.memory_version == 1


def test_is_stale_for_matching_skill():
    skill = Skill(
        name="news_crawler",
        version="1.0.0",
        output_schema=OutputSchema(fields=["title"], minimum_fields=["title"]),
    )
    mem = SkillMemory.create_for_skill("news_crawler", "1.0.0")
    assert mem.is_stale_for(skill) is False


def test_is_stale_for_mismatched_skill():
    skill = Skill(
        name="news_crawler",
        version="2.0.0",
        output_schema=OutputSchema(fields=["title"], minimum_fields=["title"]),
    )
    mem = SkillMemory.create_for_skill("news_crawler", "1.0.0")
    assert mem.is_stale_for(skill) is True


def test_add_signal():
    mem = SkillMemory.create_for_skill("test_skill", "1.0.0")
    signal = ImprovementSignal(
        signal_type="api_pattern",
        url="https://example.com",
        hint="/api/v2/data",
        prompt_source="prompt1",
    )
    mem.add_signal(signal)
    assert mem.pending_signal_count() == 1


def test_improvement_signal_defaults():
    signal = ImprovementSignal(signal_type="dom_selector")
    assert signal.confidence == 0.5
    assert signal.url == ""
    assert signal.platform is None


def test_skill_memory_serialization():
    mem = SkillMemory.create_for_skill("finance_crawler", "1.0.0")
    data = mem.model_dump(mode="json")
    assert data["skill_name"] == "finance_crawler"
    assert isinstance(data["pending_signals"], list)
    assert isinstance(data["platform_fingerprints"], dict)


def test_consolidation_log_entry():
    entry = ConsolidationLogEntry(
        triggered_by="batch",
        signal_count=50,
        signals_processed=50,
        memory_version_before=1,
        memory_version_after=2,
        cost_usd=0.005,
    )
    assert entry.triggered_by == "batch"
    assert entry.memory_version_after == 2
