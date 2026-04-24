"""
UnitRecord — canonical unit record. Forward-compatible with Phase B PostgreSQL.
"""

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class DataQualityFlag(StrEnum):
    CLEAN = "CLEAN"
    SMOOTHED = "SMOOTHED"
    CARRIED_FORWARD = "CARRIED_FORWARD"
    QA_HELD = "QA_HELD"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UnitRecord(BaseModel):
    unit_id: str | None = None
    property_id: str
    unit_number: str
    floor_plan_id: str | None = None
    floor: int | None = None
    building: str | None = None
    sqft: int | None = None
    floor_plan_type: str | None = None
    asking_rent: float | None = None
    effective_rent: float | None = None
    concession: dict[str, Any] | None = None
    availability_status: AvailabilityStatus = AvailabilityStatus.UNKNOWN
    availability_date: date | None = None
    days_on_market: int | None = None
    availability_periods: list[dict[str, Any]] = Field(default_factory=list)
    scrape_timestamp: datetime = Field(default_factory=_utcnow)
    extraction_tier: int | None = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    data_quality_flag: DataQualityFlag = DataQualityFlag.CLEAN
    source: str = "DIRECT_SITE"
    carryforward_days: int = 0
