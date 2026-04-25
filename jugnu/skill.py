from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class LiteLLMSettings(BaseModel):
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.0
    max_tokens: int = 4096
    timeout_seconds: int = 60
    max_retries: int = 2
    extra_params: dict = Field(default_factory=dict)


class VisionLLMSettings(BaseModel):
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.0
    max_tokens: int = 2048
    timeout_seconds: int = 60
    max_retries: int = 2


class ScreenshotSettings(BaseModel):
    enabled: bool = False
    full_page: bool = True
    max_screenshots_per_url: int = 2
    width: int = 1280
    height: int = 900


class OutputSchema(BaseModel):
    fields: list[str]
    primary_key: Optional[str] = None
    merging_keys: list[str] = []
    minimum_fields: list[str]
    json_schema: dict = Field(default_factory=dict)


class SourceHint(BaseModel):
    platform: Optional[str] = None
    api_patterns: list[str] = []
    link_keywords: list[str] = []
    dom_selectors: dict[str, str] = {}


class JugnuSettings(BaseModel):
    link_confidence_threshold: float = 0.4
    max_external_depth: int = 0
    max_llm_calls_per_url: int = 3
    max_concurrent_crawls: int = 0
    carry_forward_on_failure: bool = True
    memory_consolidation_batch_size: int = 50
    memory_consolidation_smart_trigger_count: int = 3


class Skill(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    output_schema: OutputSchema
    source_hints: list[SourceHint] = []
    llm_settings: LiteLLMSettings = Field(default_factory=LiteLLMSettings)
    vision_settings: VisionLLMSettings = Field(default_factory=VisionLLMSettings)
    screenshot_settings: ScreenshotSettings = Field(default_factory=ScreenshotSettings)
    jugnu_settings: JugnuSettings = Field(default_factory=JugnuSettings)
    custom_instructions: str = ""
    negative_keywords: list[str] = []
