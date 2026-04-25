"""SLO watcher — checks run-level metrics against thresholds.

Pure logic, no I/O. Raises alerts as SloViolation dataclasses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SloThresholds:
    """Configurable SLO thresholds."""

    success_rate_min: float = 0.95
    llm_cost_per_run_max_usd: float = 1.00
    vision_fallback_max_pct: float = 0.05
    drift_noise_max_pct: float = 0.02


@dataclass(frozen=True)
class SloViolation:
    """A single SLO threshold breach."""

    name: str
    threshold: float
    observed: float
    sample: list[str] = field(default_factory=list)


def check(
    cost_rollup: dict[str, float],
    property_results: list[dict[str, Any]],
    thresholds: SloThresholds | None = None,
) -> list[SloViolation]:
    """Check run-level metrics against SLO thresholds."""
    if thresholds is None:
        thresholds = SloThresholds()

    violations: list[SloViolation] = []
    total = len(property_results) or 1

    def _failed(p: dict[str, Any]) -> bool:
        meta = p.get("_meta", {}) or {}
        verdict = str(meta.get("verdict") or "")
        if verdict.startswith("FAILED"):
            return True
        tier_legacy = str(meta.get("scrape_tier_used") or "")
        return "FAIL" in tier_legacy.upper()

    def _tier(p: dict[str, Any]) -> str:
        meta = p.get("_meta", {}) or {}
        extract_result = p.get("_extract_result") or {}
        tier_from_extract = (
            extract_result.get("tier_used")
            if isinstance(extract_result, dict)
            else getattr(extract_result, "tier_used", None)
        )
        return str(meta.get("scrape_tier_used") or tier_from_extract or "")

    failed = sum(1 for p in property_results if _failed(p))
    success_rate = 1.0 - (failed / total)
    if success_rate < thresholds.success_rate_min:
        fail_cids = [
            (p.get("_meta", {}) or {}).get("canonical_id", "?") for p in property_results if _failed(p)
        ][:5]
        violations.append(
            SloViolation(
                name="success_rate",
                threshold=thresholds.success_rate_min,
                observed=round(success_rate, 4),
                sample=fail_cids,
            )
        )

    llm_cost = cost_rollup.get("llm", 0.0) + cost_rollup.get("vision", 0.0)
    if llm_cost > thresholds.llm_cost_per_run_max_usd:
        violations.append(
            SloViolation(
                name="llm_cost_per_run",
                threshold=thresholds.llm_cost_per_run_max_usd,
                observed=round(llm_cost, 4),
            )
        )

    vision_used = sum(1 for p in property_results if "vision" in _tier(p).lower())
    vision_pct = vision_used / total
    if vision_pct > thresholds.vision_fallback_max_pct:
        violations.append(
            SloViolation(
                name="vision_fallback_rate",
                threshold=thresholds.vision_fallback_max_pct,
                observed=round(vision_pct, 4),
            )
        )

    flagged = sum(1 for p in property_results if p.get("_meta", {}).get("flagged"))
    drift_pct = flagged / total
    if drift_pct > thresholds.drift_noise_max_pct:
        violations.append(
            SloViolation(
                name="drift_noise",
                threshold=thresholds.drift_noise_max_pct,
                observed=round(drift_pct, 4),
            )
        )

    return violations
