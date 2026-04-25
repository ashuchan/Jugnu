"""
Self-learning scrape profile model.

Per-property profile that learns CSS selectors, API endpoints, and JSON paths
from LLM extraction (Tier 4). On subsequent runs the profile drives deterministic
extraction without LLM calls.
"""

from __future__ import annotations

import urllib.parse
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProfileMaturity(StrEnum):
    COLD = "COLD"
    WARM = "WARM"
    HOT = "HOT"


class BlockedEndpoint(BaseModel):
    model_config = ConfigDict(extra="ignore")
    url_pattern: str
    reason: str = ""
    blocked_at: datetime = Field(default_factory=datetime.utcnow)
    attempts: int = 1


class LlmFieldMapping(BaseModel):
    model_config = ConfigDict(extra="ignore")
    api_url_pattern: str
    json_paths: dict[str, str] = Field(default_factory=dict)
    response_envelope: str = ""
    discovered_at: datetime = Field(default_factory=datetime.utcnow)
    success_count: int = 0


class ApiEndpoint(BaseModel):
    model_config = ConfigDict(extra="ignore")
    url_pattern: str
    json_paths: dict[str, str] = Field(default_factory=dict)
    provider: str | None = None


class FieldSelectorMap(BaseModel):
    model_config = ConfigDict(extra="ignore")
    container: str | None = None
    unit_id: str | None = None
    rent: str | None = None
    sqft: str | None = None
    bedrooms: str | None = None
    bathrooms: str | None = None
    availability_status: str | None = None
    availability_date: str | None = None
    floor_plan_name: str | None = None


class ExpanderAction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    selector: str
    action: str = "click"


class NavigationConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    entry_url: str | None = None
    availability_page_path: str | None = None
    winning_page_url: str | None = None
    requires_interaction: list[ExpanderAction] = Field(default_factory=list)
    timeout_ms: int = 60000
    block_resource_domains: list[str] = Field(default_factory=list)
    availability_links: list[str] = Field(default_factory=list)
    explored_links: list[str] = Field(default_factory=list)

    @field_validator("explored_links", mode="before")
    @classmethod
    def cap_explored_links(cls, v: list[str]) -> list[str]:
        if isinstance(v, list) and len(v) > 50:
            return v[:50]
        return v


class ApiHints(BaseModel):
    model_config = ConfigDict(extra="ignore")
    known_endpoints: list[ApiEndpoint] = Field(default_factory=list)
    widget_endpoints: list[str] = Field(default_factory=list)
    api_provider: str | None = "unknown"
    client_account_id: str | None = None
    wait_for_url_pattern: str | None = None
    blocked_endpoints: list[BlockedEndpoint] = Field(default_factory=list)
    llm_field_mappings: list[LlmFieldMapping] = Field(default_factory=list)

    @field_validator("blocked_endpoints", mode="before")
    @classmethod
    def cap_blocked_endpoints(cls, v: list[object]) -> list[object]:
        if isinstance(v, list) and len(v) > 50:
            return v[:50]
        return v

    @field_validator("llm_field_mappings", mode="before")
    @classmethod
    def cap_llm_field_mappings(cls, v: list[object]) -> list[object]:
        if isinstance(v, list) and len(v) > 20:
            return v[:20]
        return v


class DomHints(BaseModel):
    model_config = ConfigDict(extra="ignore")
    platform_detected: str | None = None
    field_selectors: FieldSelectorMap = Field(default_factory=FieldSelectorMap)
    jsonld_present: bool = False
    availability_page_sections: list[str] = Field(default_factory=list)


class ExtractionConfidence(BaseModel):
    model_config = ConfigDict(extra="ignore")
    preferred_tier: int | None = None
    last_success_tier: int | None = None
    consecutive_successes: int = 0
    consecutive_failures: int = 0
    last_unit_count: int = 0
    maturity: ProfileMaturity = ProfileMaturity.COLD
    last_success_detection: Any = None
    consecutive_unreachable: int = 0


class LlmArtifacts(BaseModel):
    model_config = ConfigDict(extra="ignore")
    extraction_prompt_hash: str | None = None
    field_mapping_notes: str | None = None
    api_schema_signature: str | None = None
    dom_structure_hash: str | None = None
    last_api_analysis_results: dict[str, str] = Field(default_factory=dict)


class ProfileStats(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total_scrapes: int = 0
    total_successes: int = 0
    total_failures: int = 0
    total_llm_calls: int = 0
    total_llm_cost_usd: float = 0.0
    last_tier_used: str | None = None
    last_unit_count: int = 0
    p50_scrape_duration_ms: int | None = None
    p95_scrape_duration_ms: int | None = None
    consecutive_llm_rescue_failures: int = 0


class ScrapeProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    canonical_id: str
    version: int = 2
    schema_version: str = "v2"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: str = "BOOTSTRAP"
    navigation: NavigationConfig = Field(default_factory=NavigationConfig)
    api_hints: ApiHints = Field(default_factory=ApiHints)
    dom_hints: DomHints = Field(default_factory=DomHints)
    confidence: ExtractionConfidence = Field(default_factory=ExtractionConfidence)
    llm_artifacts: LlmArtifacts = Field(default_factory=LlmArtifacts)
    stats: ProfileStats = Field(default_factory=ProfileStats)


def detect_platform(url: str) -> str | None:
    """Detect PMS platform from URL patterns."""
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or ""
    path = parsed.path or ""
    if "rentcafe.com" in host or ("/apartments/" in path and "/default.aspx" in path):
        return "rentcafe"
    if "entrata" in host:
        return "entrata"
    if "appfolio" in host:
        return "appfolio"
    if "sightmap" in host:
        return "sightmap"
    if "realpage" in host:
        return "realpage"
    return None
