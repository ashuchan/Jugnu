from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ProfileMaturity(StrEnum):
    COLD = "cold"
    LEARNING = "learning"
    WARM = "warm"
    STABLE = "stable"


class ApiHints(BaseModel):
    confirmed_endpoints: list[str] = []
    confirmed_patterns: list[str] = []
    blocked_endpoints: list[str] = []
    auth_required: bool = False
    pagination_style: str | None = None
    response_format: str | None = None


class DomHints(BaseModel):
    confirmed_selectors: dict[str, str] = {}
    list_container_selectors: list[str] = []
    pagination_selectors: list[str] = []
    noise_selectors: list[str] = []


class NavigationConfig(BaseModel):
    requires_interaction: bool = False
    scroll_for_content: bool = False
    wait_for_selector: str | None = None
    wait_ms: int = 0
    external_sources: list[str] = []
    pre_crawl_steps: list[dict] = []


class ProfileStats(BaseModel):
    total_crawls: int = 0
    successful_crawls: int = 0
    total_records_extracted: int = 0
    avg_confidence: float = 0.0
    last_crawl_timestamp: str | None = None
    avg_latency_ms: float = 0.0


class LlmFieldMapping(BaseModel):
    field_name: str
    extraction_hint: str = ""
    synonyms: list[str] = []
    confidence: float = 0.0
    last_seen: str | None = None
    # Replay metadata — populated by Spark.crystallizer from Prompt-2's
    # field_mappings.api/dom blocks so Tier-1a can re-issue the request next
    # run without calling the LLM.
    api_url_pattern: str | None = None
    json_paths: dict[str, str] = {}
    response_envelope: str | None = None
    dom_selector: str | None = None
    success_count: int = 0


class ScrapeProfile(BaseModel):
    url_pattern: str
    platform: str | None = None
    maturity: ProfileMaturity = ProfileMaturity.COLD
    preferred_tier: str = ""
    api_hints: ApiHints = Field(default_factory=ApiHints)
    dom_hints: DomHints = Field(default_factory=DomHints)
    navigation_config: NavigationConfig = Field(default_factory=NavigationConfig)
    field_mappings: list[LlmFieldMapping] = []
    stats: ProfileStats = Field(default_factory=ProfileStats)
    fingerprint_hash: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
