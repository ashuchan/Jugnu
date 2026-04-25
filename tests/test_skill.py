from __future__ import annotations

import pytest
from pydantic import ValidationError

from jugnu.skill import (
    JugnuSettings,
    LiteLLMSettings,
    OutputSchema,
    ScreenshotSettings,
    Skill,
    SourceHint,
    VisionLLMSettings,
)


def test_output_schema_basic():
    schema = OutputSchema(fields=["title", "price"], minimum_fields=["title"])
    assert schema.fields == ["title", "price"]
    assert schema.primary_key is None
    assert schema.merging_keys == []


def test_output_schema_with_primary_key():
    schema = OutputSchema(
        fields=["id", "name"],
        primary_key="id",
        minimum_fields=["id", "name"],
    )
    assert schema.primary_key == "id"


def test_source_hint_defaults():
    hint = SourceHint()
    assert hint.platform is None
    assert hint.api_patterns == []
    assert hint.link_keywords == []
    assert hint.dom_selectors == {}


def test_source_hint_with_values():
    hint = SourceHint(
        platform="wordpress",
        api_patterns=["/wp-json/"],
        link_keywords=["article", "post"],
        dom_selectors={"title": "h1.entry-title"},
    )
    assert hint.platform == "wordpress"
    assert "/wp-json/" in hint.api_patterns


def test_jugnu_settings_defaults():
    settings = JugnuSettings()
    assert settings.link_confidence_threshold == 0.4
    assert settings.max_external_depth == 0
    assert settings.max_llm_calls_per_url == 3
    assert settings.max_concurrent_crawls == 0
    assert settings.carry_forward_on_failure is True
    assert settings.memory_consolidation_batch_size == 50
    assert settings.memory_consolidation_smart_trigger_count == 3


def test_skill_creation():
    skill = Skill(
        name="test_crawler",
        version="1.0.0",
        output_schema=OutputSchema(fields=["title", "price"], minimum_fields=["title"]),
    )
    assert skill.name == "test_crawler"
    assert skill.version == "1.0.0"
    assert len(skill.source_hints) == 0


def test_skill_serialization():
    skill = Skill(
        name="test_crawler",
        output_schema=OutputSchema(fields=["title"], minimum_fields=["title"]),
    )
    data = skill.model_dump(mode="json")
    assert data["name"] == "test_crawler"
    assert "output_schema" in data
    assert "llm_settings" in data


def test_skill_with_source_hints():
    skill = Skill(
        name="news_crawler",
        output_schema=OutputSchema(fields=["headline", "author"], minimum_fields=["headline"]),
        source_hints=[SourceHint(link_keywords=["news", "article"])],
    )
    assert len(skill.source_hints) == 1
    assert "news" in skill.source_hints[0].link_keywords


def test_litellm_settings_defaults():
    s = LiteLLMSettings()
    assert s.temperature == 0.0
    assert s.max_tokens == 4096
    assert s.max_retries == 2


def test_output_schema_requires_fields():
    with pytest.raises(ValidationError):
        OutputSchema(minimum_fields=["title"])  # type: ignore[call-arg]
