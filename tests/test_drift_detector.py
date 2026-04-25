from __future__ import annotations

from jugnu.drift_detector import (
    apply_demotion,
    compute_page_fingerprint,
    detect_drift,
    detect_schema_drift,
    update_fingerprint,
)
from jugnu.profile import ProfileMaturity, ScrapeProfile


def test_compute_page_fingerprint_deterministic():
    fp = compute_page_fingerprint("<html>hi</html>")
    assert len(fp) == 32
    assert fp == compute_page_fingerprint("<html>hi</html>")


def test_update_fingerprint_sets_hash():
    p = ScrapeProfile(url_pattern="https://example.com")
    update_fingerprint(p, "<html>x</html>")
    assert p.fingerprint_hash is not None


def test_detect_schema_drift_no_baseline_is_false():
    p = ScrapeProfile(url_pattern="https://example.com")
    assert detect_schema_drift(p, "abc") is False


def test_detect_drift_record_count_drop():
    p = ScrapeProfile(url_pattern="https://example.com", maturity=ProfileMaturity.STABLE)
    new = [{"title": "a"}] * 3
    report = detect_drift(p, new, minimum_fields=["title"], last_record_count=10)
    assert report.drifted is True
    assert any("record_count_drop" in r for r in report.reasons)


def test_detect_drift_all_null_minimum_fields():
    p = ScrapeProfile(url_pattern="https://example.com", maturity=ProfileMaturity.WARM)
    new = [{"title": None, "price": None}, {"title": "", "price": None}]
    report = detect_drift(p, new, minimum_fields=["title", "price"])
    assert report.drifted is True
    assert "all_minimum_fields_null" in report.reasons


def test_detect_drift_zero_records_on_mature_profile():
    p = ScrapeProfile(url_pattern="https://example.com", maturity=ProfileMaturity.WARM)
    report = detect_drift(p, [], minimum_fields=["title"])
    assert report.drifted is True
    assert "zero_records_on_mature_profile" in report.reasons


def test_detect_drift_no_drift_on_cold_profile_zero_records():
    p = ScrapeProfile(url_pattern="https://example.com", maturity=ProfileMaturity.COLD)
    report = detect_drift(p, [], minimum_fields=["title"])
    assert report.drifted is False


def test_apply_demotion_steps_one_level():
    p = ScrapeProfile(url_pattern="https://example.com", maturity=ProfileMaturity.STABLE)
    p2 = ScrapeProfile(url_pattern="https://example.com", maturity=ProfileMaturity.WARM)
    p3 = ScrapeProfile(url_pattern="https://example.com", maturity=ProfileMaturity.LEARNING)

    rep_stable = detect_drift(p, [], minimum_fields=["title"])
    rep_warm = detect_drift(p2, [], minimum_fields=["title"])
    # LEARNING wouldn't have drifted via the zero-record signal — synthesize one
    rep_learn = detect_drift(p3, [{"title": None}], minimum_fields=["title"], last_record_count=10)

    apply_demotion(p, rep_stable)
    apply_demotion(p2, rep_warm)
    apply_demotion(p3, rep_learn)
    assert p.maturity == ProfileMaturity.WARM
    assert p2.maturity == ProfileMaturity.LEARNING
    assert p3.maturity == ProfileMaturity.COLD


def test_apply_demotion_noop_when_not_drifted():
    p = ScrapeProfile(url_pattern="https://example.com", maturity=ProfileMaturity.WARM)
    report = detect_drift(p, [{"title": "ok"}], minimum_fields=["title"], last_record_count=1)
    apply_demotion(p, report)
    assert p.maturity == ProfileMaturity.WARM
