"""Drift detection — detect schema drift from page fingerprint, unit-count drops,
and all-null minimum-field results. Demotes profiles when drift is confirmed.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from jugnu.profile import ProfileMaturity, ScrapeProfile


@dataclass
class DriftReport:
    drifted: bool
    reasons: list[str]
    suggested_demotion: ProfileMaturity | None = None


def compute_page_fingerprint(html: str) -> str:
    return hashlib.sha256(html.encode()).hexdigest()[:32]


def update_fingerprint(profile: ScrapeProfile, html: str) -> ScrapeProfile:
    profile.fingerprint_hash = compute_page_fingerprint(html)
    return profile


def detect_schema_drift(
    profile: ScrapeProfile,
    current_fingerprint: str,
) -> bool:
    """Return True if the page fingerprint changed from profile baseline.

    Returns False when no baseline is recorded — first scrape shouldn't trip drift.
    """
    stored = profile.fingerprint_hash
    if stored is None:
        return False
    return stored != current_fingerprint


def detect_drift(
    profile: ScrapeProfile,
    current_records: list[dict],
    minimum_fields: list[str],
    last_record_count: int | None = None,
    drop_threshold: float = 0.5,
) -> DriftReport:
    """Detect drift from extracted records vs profile expectations.

    Three signals:
      1. Record count dropped >= drop_threshold vs last_record_count.
      2. All records null on every minimum_field (extraction broke).
      3. Zero records when profile is WARM/STABLE (regression vs maturity).
    """
    reasons: list[str] = []

    # Signal 1: count drop
    if last_record_count is not None and last_record_count > 0:
        ratio = (last_record_count - len(current_records)) / last_record_count
        if ratio >= drop_threshold:
            reasons.append(f"record_count_drop:{ratio:.2f}")

    # Signal 2: all-null on minimum fields
    if current_records and minimum_fields:
        all_null = all(
            all(rec.get(f) in (None, "") for f in minimum_fields)
            for rec in current_records
        )
        if all_null:
            reasons.append("all_minimum_fields_null")

    # Signal 3: regression on a profile that was WARM/STABLE
    if not current_records and profile.maturity in (ProfileMaturity.WARM, ProfileMaturity.STABLE):
        reasons.append("zero_records_on_mature_profile")

    drifted = bool(reasons)
    suggested = _suggest_demotion(profile.maturity) if drifted else None
    return DriftReport(drifted=drifted, reasons=reasons, suggested_demotion=suggested)


def _suggest_demotion(current: ProfileMaturity) -> ProfileMaturity:
    """One-step demotion ladder."""
    return {
        ProfileMaturity.STABLE: ProfileMaturity.WARM,
        ProfileMaturity.WARM: ProfileMaturity.LEARNING,
        ProfileMaturity.LEARNING: ProfileMaturity.COLD,
        ProfileMaturity.COLD: ProfileMaturity.COLD,
    }[current]


def apply_demotion(profile: ScrapeProfile, report: DriftReport) -> ScrapeProfile:
    """Mutate profile maturity per drift report. No-op if not drifted."""
    if not report.drifted or report.suggested_demotion is None:
        return profile
    profile.maturity = report.suggested_demotion
    return profile
