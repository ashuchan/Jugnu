from __future__ import annotations

from enum import StrEnum
from typing import Optional
from pydantic import BaseModel, Field


class ProfileMaturity(StrEnum):
    COLD = "cold"
    LEARNING = "learning"
    WARM = "warm"
    STABLE = "stable"


class ApiHints(BaseModel):
    confirmed_endpoints: list[str] = []
    confirmed_patterns: list[str] = []
    auth_required: bool = False
    pagination_style: Optional[str] = None
    response_format: Optional[str] = None


class DomHints(BaseModel):
    confirmed_selectors: dict[str, str] = {}
    list_container_selectors: list[str] = []
    pagination_selectors: list[str] = []
    noise_selectors: list[str] = []


class NavigationConfig(BaseModel):
    requires_interaction: bool = False
    scroll_for_content: bool = False
    wait_for_selector: Optional[str] = None
    wait_ms: int = 0
    external_sources: list[str] = []
    pre_crawl_steps: list[dict] = []


class ProfileStats(BaseModel):
    total_crawls: int = 0
    successful_crawls: int = 0
    total_records_extracted: int = 0
    avg_confidence: float = 0.0
    last_crawl_timestamp: Optional[str] = None
    avg_latency_ms: float = 0.0


class LlmFieldMapping(BaseModel):
    field_name: str
    extraction_hint: str = ""
    synonyms: list[str] = []
    confidence: float = 0.0
    last_seen: Optional[str] = None


class ScrapeProfile(BaseModel):
    url_pattern: str
    platform: Optional[str] = None
    maturity: ProfileMaturity = ProfileMaturity.COLD
    preferred_tier: str = ""
    api_hints: ApiHints = Field(default_factory=ApiHints)
    dom_hints: DomHints = Field(default_factory=DomHints)
    navigation_config: NavigationConfig = Field(default_factory=NavigationConfig)
    field_mappings: list[LlmFieldMapping] = []
    stats: ProfileStats = Field(default_factory=ProfileStats)
    fingerprint_hash: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
