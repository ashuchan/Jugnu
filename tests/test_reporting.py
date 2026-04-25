from __future__ import annotations

from pathlib import Path

from jugnu.contracts import Blink, CrawlStatus
from jugnu.observability.cost_ledger import CostLedger
from jugnu.reporting.blink_report import generate_blink_report
from jugnu.reporting.llm_cost_report import build_cost_report
from jugnu.reporting.run_report import build_run_report
from jugnu.spark.skill_memory import ConsolidationLogEntry, SkillMemory


def test_generate_blink_report_includes_status_and_records():
    blink = Blink(
        url="https://example.com",
        status=CrawlStatus.SUCCESS,
        records=[{"title": "a"}, {"title": "b"}],
        tier_used="json_ld",
        confidence=0.91,
        llm_cost_usd=0.05,
    )
    md = generate_blink_report(blink, consolidations_triggered=2)
    assert "https://example.com" in md
    assert "json_ld" in md
    assert "2" in md
    assert "**Records:** 2" in md


def test_build_run_report_counts_status_and_tracks_memory():
    memory = SkillMemory.create_for_skill("news", "1.0.0")
    memory.memory_version = 3
    memory.total_consolidation_cost_usd = 0.04
    memory.consolidation_log.append(
        ConsolidationLogEntry(
            triggered_by="batch",
            signal_count=50,
            signals_processed=50,
            memory_version_before=2,
            memory_version_after=3,
            cost_usd=0.04,
        )
    )
    results = {
        "https://a.com": Blink(url="https://a.com", status=CrawlStatus.SUCCESS, records=[{"x": 1}], tier_used="json_ld"),
        "https://b.com": Blink(url="https://b.com", status=CrawlStatus.FAILED, records=[]),
        "https://c.com": Blink(url="https://c.com", status=CrawlStatus.CARRY_FORWARD, records=[{"x": 2}]),
    }
    report = build_run_report(results, skill_name="news", memory=memory, warmup_cost_usd=0.01)
    assert "success: 1" in report
    assert "failed: 1" in report
    assert "carry_forward: 1" in report
    assert "memory_version: 3" in report
    assert "json_ld" in report


def test_build_cost_report_renders_aggregations(tmp_path: Path):
    ledger = CostLedger(tmp_path / "cost.db")
    ledger.record(stage="prompt1", cost_usd=0.10, url="u", skill="s", model="m1")
    ledger.record(stage="prompt2", cost_usd=0.20, url="u", skill="s", model="m1")
    md = build_cost_report(ledger, skill="s")
    assert "**Total:** $0.3000" in md
    assert "prompt2" in md
    assert "prompt1" in md
    assert "m1" in md
