"""
ExtractionResult model — output of any extraction tier.
"""

from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ExtractionTier(IntEnum):
    API_INTERCEPTION = 1
    JSON_LD = 2
    PLAYWRIGHT_TPL = 3
    LLM_GPT4O_MINI = 4
    VISION_FALLBACK = 5


class ExtractionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ExtractionResult(BaseModel):
    property_id: str
    tier: ExtractionTier | None = None
    status: ExtractionStatus
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_fields: dict[str, Any] = Field(default_factory=dict)
    field_confidences: dict[str, float] = Field(default_factory=dict)
    low_confidence_fields: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=_utcnow)
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        """True only if status SUCCESS and confidence meets 0.7 threshold."""
        return self.status == ExtractionStatus.SUCCESS and self.confidence_score >= 0.7
