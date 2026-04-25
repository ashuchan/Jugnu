from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

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
    """Per-URL input. `previous_records` enables Prompt-3 merge mode; if non-empty
    AND new records are extracted, the crawler invokes the merge LLM to decide
    which new records map to existing ones. `scrape_profile` is the per-URL
    learned profile from a prior run — None on first visit.
    """

    url: str
    seed_url: str | None = None
    carry_forward_records: list[dict] = field(default_factory=list)
    previous_records: list[dict] = field(default_factory=list)
    scrape_profile: ScrapeProfile | None = None
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
    error: str | None = None
    screenshot: bytes | None = None

    @property
    def success(self) -> bool:
        return self.error is None and 200 <= self.status_code < 300


@dataclass
class AdapterResult:
    records: list[dict] = field(default_factory=list)
    tier_used: str = ""
    confidence: float = 0.0
    raw_payload: str | None = None
    error: str | None = None
    llm_cost_usd: float = 0.0
    llm_interactions: list[dict] = field(default_factory=list)


@dataclass
class Blink:
    url: str
    status: CrawlStatus
    records: list[dict]
    scrape_profile: ScrapeProfile | None = None
    llm_profile: SkillMemory | None = None
    tier_used: str = ""
    confidence: float = 0.0
    carry_forward_days: int = 0
    llm_cost_usd: float = 0.0
    llm_interactions: list[dict] = field(default_factory=list)
    report_md: str = ""
    screenshots: list[bytes] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
