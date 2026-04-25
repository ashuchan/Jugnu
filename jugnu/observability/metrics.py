from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from jugnu.contracts import Blink, CrawlStatus


@dataclass
class CrawlMetrics:
    skill_name: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    total_urls: int = 0
    succeeded: int = 0
    failed: int = 0
    carry_forward: int = 0
    total_records: int = 0
    total_llm_cost_usd: float = 0.0
    avg_confidence: float = 0.0
    dlq_size: int = 0

    @classmethod
    def from_results(
        cls,
        results: dict[str, Blink],
        skill_name: str = "",
        dlq_size: int = 0,
    ) -> "CrawlMetrics":
        m = cls(skill_name=skill_name)
        m.completed_at = datetime.now(timezone.utc).isoformat()
        m.total_urls = len(results)
        m.dlq_size = dlq_size
        total_conf = 0.0
        for blink in results.values():
            if blink.status == CrawlStatus.SUCCESS:
                m.succeeded += 1
            elif blink.status == CrawlStatus.CARRY_FORWARD:
                m.carry_forward += 1
            else:
                m.failed += 1
            m.total_records += len(blink.records)
            m.total_llm_cost_usd += blink.llm_cost_usd
            total_conf += blink.confidence
        if m.total_urls:
            m.avg_confidence = total_conf / m.total_urls
        return m

    def summary(self) -> str:
        return (
            f"Crawl complete: {self.total_urls} URLs, "
            f"{self.succeeded} succeeded, {self.failed} failed, "
            f"{self.total_records} records, cost=${self.total_llm_cost_usd:.4f}"
        )
