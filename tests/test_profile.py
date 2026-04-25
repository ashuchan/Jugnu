from __future__ import annotations

import pytest

from jugnu.dlq import DeadLetterQueue, DlqEntry
from jugnu.drift_detector import compute_page_fingerprint, detect_schema_drift, update_fingerprint
from jugnu.profile import ProfileMaturity, ScrapeProfile
from jugnu.profile_updater import ProfileUpdater
from jugnu.spark.skill_memory import ImprovementSignal
from jugnu.validation.cross_run_sanity import sanity_check
from jugnu.validation.identity_fallback import assign_identities
from jugnu.validation.schema_gate import passes_schema_gate, validate_primary_key_uniqueness
from jugnu.skill import OutputSchema


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
    # Simulate 5 crawls
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


def test_schema_gate_passes():
    schema = OutputSchema(fields=["title", "price"], minimum_fields=["title"])
    records = [{"title": "Item 1", "price": "$10"}, {"title": "Item 2"}]
    passes, reason = passes_schema_gate(records, schema)
    assert passes is True


def test_schema_gate_fails_empty():
    schema = OutputSchema(fields=["title"], minimum_fields=["title"])
    passes, reason = passes_schema_gate([], schema)
    assert passes is False
    assert "no_records" in reason


def test_identity_fallback_assigns_id():
    records = [{"title": "A"}, {"title": "B"}]
    result = assign_identities(records)
    assert all("_id" in r for r in result)
    assert result[0]["_id"] != result[1]["_id"]


def test_cross_run_sanity_drop():
    old = [{"title": str(i)} for i in range(100)]
    new = [{"title": str(i)} for i in range(30)]
    passes, reason = sanity_check(new, old)
    assert passes is False
    assert "drop" in reason
