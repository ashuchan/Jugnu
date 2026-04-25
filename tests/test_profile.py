from __future__ import annotations

from jugnu.dlq import DeadLetterQueue
from jugnu.drift_detector import detect_schema_drift
from jugnu.profile import ProfileMaturity, ScrapeProfile
from jugnu.profile_updater import ProfileUpdater
from jugnu.spark.skill_memory import ImprovementSignal


def test_profile_defaults():
    p = ScrapeProfile(url_pattern="https://example.com/*")
    assert p.maturity == ProfileMaturity.COLD
    assert p.platform is None
    assert p.stats.total_crawls == 0


def test_profile_updater_apply_api_signal():
    p = ScrapeProfile(url_pattern="https://example.com/*")
    updater = ProfileUpdater()
    signal = ImprovementSignal(signal_type="api_pattern", hint="/api/v2/items")
    updated = updater.apply_signals(p, [signal])
    assert "/api/v2/items" in updated.api_hints.confirmed_patterns


def test_profile_updater_maturity_progression():
    p = ScrapeProfile(url_pattern="https://example.com/*")
    updater = ProfileUpdater()
    for _ in range(5):
        updater.apply_signals(p, [])
    assert p.maturity in (ProfileMaturity.WARM, ProfileMaturity.STABLE)


def test_drift_detector_no_fingerprint():
    p = ScrapeProfile(url_pattern="https://example.com/*")
    assert detect_schema_drift(p, "abc123") is False


def test_drift_detector_changed():
    p = ScrapeProfile(url_pattern="https://example.com/*", fingerprint_hash="old_hash")
    assert detect_schema_drift(p, "new_hash") is True


def test_dlq_push_and_pop():
    dlq = DeadLetterQueue()
    dlq.push("https://example.com", "timeout")
    assert dlq.size() == 1
    entries = dlq.pop_all()
    assert len(entries) == 1
    assert entries[0].url == "https://example.com"
    assert dlq.is_empty()
