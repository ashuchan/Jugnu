"""
ScrapeEvent — append-only audit record for every scrape attempt.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class ChangeDetectionResult(StrEnum):
    CHANGED = "CHANGED"
    UNCHANGED = "UNCHANGED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ScrapeOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class ScrapeEvent(BaseModel):
    event_id: str
    property_id: str
    scrape_timestamp: datetime
    extraction_tier: int | None = None
    change_detection_result: ChangeDetectionResult | None = None
    scrape_outcome: ScrapeOutcome
    failure_reason: str | None = None
    page_load_ms: int | None = None
    proxy_used: bool = False
    proxy_provider: str | None = None
    vision_fallback_used: bool = False
    banner_capture_attempted: bool = False
    banner_concession_found: bool = False
    accuracy_sample_selected: bool = False
    raw_html_path: str | None = None
    screenshot_path: str | None = None
    confidence_score: float | None = None
