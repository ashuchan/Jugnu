"""Pydantic v2 data models. Forward-compatible with Phase B PostgreSQL schema."""

from .extraction_result import ExtractionResult, ExtractionStatus, ExtractionTier
from .scrape_event import ChangeDetectionResult, ScrapeEvent, ScrapeOutcome
from .unit_record import AvailabilityStatus, DataQualityFlag, UnitRecord

__all__ = [
    "AvailabilityStatus",
    "ChangeDetectionResult",
    "DataQualityFlag",
    "ExtractionResult",
    "ExtractionStatus",
    "ExtractionTier",
    "ScrapeEvent",
    "ScrapeOutcome",
    "UnitRecord",
]
