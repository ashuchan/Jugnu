from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from jugnu.profile import ProfileMaturity, ScrapeProfile
from jugnu.spark.skill_memory import ImprovementSignal


class ProfileUpdater:
    """Apply ImprovementSignals to a ScrapeProfile to evolve maturity."""

    def apply_signals(
        self,
        profile: ScrapeProfile,
        signals: list[ImprovementSignal],
    ) -> ScrapeProfile:
        for signal in signals:
            self._apply_one(profile, signal)
        profile.stats.total_crawls += 1
        profile.updated_at = datetime.now(timezone.utc).isoformat()
        profile.maturity = self._compute_maturity(profile)
        return profile

    def _apply_one(self, profile: ScrapeProfile, signal: ImprovementSignal) -> None:
        stype = signal.signal_type
        if stype == "api_pattern" and signal.hint:
            if signal.hint not in profile.api_hints.confirmed_patterns:
                profile.api_hints.confirmed_patterns.append(signal.hint)
        elif stype == "dom_selector" and signal.field_name and signal.hint:
            profile.dom_hints.confirmed_selectors[signal.field_name] = signal.hint
        elif stype == "platform" and signal.platform:
            profile.platform = signal.platform
        elif stype == "noise" and signal.hint:
            if signal.hint not in profile.dom_hints.noise_selectors:
                profile.dom_hints.noise_selectors.append(signal.hint)

    def _compute_maturity(self, profile: ScrapeProfile) -> ProfileMaturity:
        crawls = profile.stats.total_crawls
        if crawls >= 10:
            return ProfileMaturity.STABLE
        if crawls >= 5:
            return ProfileMaturity.WARM
        if crawls >= 2:
            return ProfileMaturity.LEARNING
        return ProfileMaturity.COLD

    def record_success(
        self,
        profile: ScrapeProfile,
        records_count: int,
        confidence: float,
        latency_ms: float,
    ) -> ScrapeProfile:
        stats = profile.stats
        stats.successful_crawls += 1
        stats.total_records_extracted += records_count
        n = stats.successful_crawls
        stats.avg_confidence = (
            (stats.avg_confidence * (n - 1) + confidence) / n
        )
        stats.avg_latency_ms = (
            (stats.avg_latency_ms * (n - 1) + latency_ms) / n
        )
        stats.last_crawl_timestamp = datetime.now(timezone.utc).isoformat()
        return profile
