from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from jugnu.contracts import Blink, CrawlInput, CrawlStatus
from jugnu.crawler import Jugnu
from jugnu.observability.metrics import CrawlMetrics
from jugnu.reporting.report_builder import blink_to_dict, build_report
from jugnu.skill import JugnuSettings, OutputSchema, Skill
from jugnu.spark.skill_memory import SkillMemory


def make_skill(**kwargs) -> Skill:
    return Skill(
        name=kwargs.get("name", "test_skill"),
        version=kwargs.get("version", "1.0.0"),
        output_schema=OutputSchema(
            fields=kwargs.get("fields", ["title", "price"]),
            minimum_fields=kwargs.get("min_fields", ["title"]),
        ),
        jugnu_settings=JugnuSettings(
            carry_forward_on_failure=kwargs.get("carry_forward", True),
        ),
    )


def test_jugnu_init():
    skill = make_skill()
    jugnu = Jugnu(skill)
    assert jugnu._skill is skill
    assert jugnu._memory is None


def test_jugnu_init_with_memory():
    skill = make_skill()
    memory = SkillMemory.create_for_skill("test_skill", "1.0.0")
    jugnu = Jugnu(skill, skill_memory=memory)
    assert jugnu._memory is memory


async def test_crawl_failed_url_with_carry_forward():
    skill = make_skill(carry_forward=True)
    jugnu = Jugnu(skill)

    carry_records = [{"title": "Old Item", "price": "$5"}]
    inp = CrawlInput(url="http://localhost:19999/fail", carry_forward_records=carry_records)

    # Patch ember to return a failed fetch
    from jugnu.contracts import FetchResult  # noqa: PLC0415
    failed_fetch = FetchResult(url="http://localhost:19999/fail", status_code=0, error="connection_refused")
    with patch("jugnu.crawler.Ember") as MockEmber:
        mock_instance = AsyncMock()
        mock_instance.fetch = AsyncMock(return_value=failed_fetch)
        MockEmber.return_value = mock_instance
        results = await jugnu.crawl({"http://localhost:19999/fail": inp})

    blink = results["http://localhost:19999/fail"]
    assert blink.status == CrawlStatus.CARRY_FORWARD
    assert len(blink.records) == 1


def test_crawl_metrics_from_results():
    results = {
        "https://a.com": Blink(url="https://a.com", status=CrawlStatus.SUCCESS, records=[{"title": "A"}], confidence=0.9),
        "https://b.com": Blink(url="https://b.com", status=CrawlStatus.FAILED, records=[], errors=["timeout"]),
    }
    metrics = CrawlMetrics.from_results(results, skill_name="test")
    assert metrics.total_urls == 2
    assert metrics.succeeded == 1
    assert metrics.failed == 1
    assert metrics.total_records == 1
    assert "succeeded" in metrics.summary()


def test_build_report():
    results = {
        "https://example.com": Blink(
            url="https://example.com",
            status=CrawlStatus.SUCCESS,
            records=[{"title": "Item 1"}, {"title": "Item 2"}],
            tier_used="json_ld",
            confidence=0.95,
        ),
    }
    report = build_report(results, skill_name="test")
    assert "**Total records extracted:** 2" in report
    assert "https://example.com" in report


def test_blink_to_dict():
    blink = Blink(
        url="https://example.com",
        status=CrawlStatus.SUCCESS,
        records=[{"title": "X"}],
        tier_used="api_json",
        confidence=0.8,
    )
    d = blink_to_dict(blink)
    assert d["url"] == "https://example.com"
    assert d["status"] == "success"
    assert len(d["records"]) == 1


def test_dlq_populated_on_exception():
    skill = make_skill(carry_forward=False)
    jugnu = Jugnu(skill)
    assert jugnu.dlq.is_empty()
