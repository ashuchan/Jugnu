from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from jugnu.profile import ScrapeProfile
    from jugnu.spark.skill_memory import SkillMemory


class CrawlStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    EMPTY = "empty"
    FAILED = "failed"
    CARRY_FORWARD = "carry_forward"
    BLOCKED = "blocked"
    TIMEOUT = "timeout"
    NOT_STARTED = "not_started"


@dataclass(frozen=True)
class CrawlInput:
    url: str
    seed_url: Optional[str] = None
    carry_forward_records: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class FetchResult:
    url: str
    status_code: int = 0
    html: str = ""
    text: str = ""
    content_type: str = ""
    redirect_chain: list[str] = field(default_factory=list)
    response_headers: dict = field(default_factory=dict)
    latency_ms: float = 0.0
    error: Optional[str] = None
    screenshot: Optional[bytes] = None

    @property
    def success(self) -> bool:
        return self.error is None and 200 <= self.status_code < 300


@dataclass
class AdapterResult:
    records: list[dict] = field(default_factory=list)
    tier_used: str = ""
    confidence: float = 0.0
    raw_payload: Optional[str] = None
    error: Optional[str] = None
    llm_cost_usd: float = 0.0
    llm_interactions: list[dict] = field(default_factory=list)


@dataclass
class Blink:
    url: str
    status: CrawlStatus
    records: list[dict]
    scrape_profile: Optional["ScrapeProfile"] = None
    llm_profile: Optional["SkillMemory"] = None
    tier_used: str = ""
    confidence: float = 0.0
    carry_forward_days: int = 0
    llm_cost_usd: float = 0.0
    llm_interactions: list[dict] = field(default_factory=list)
    report_md: str = ""
    screenshots: list[bytes] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
