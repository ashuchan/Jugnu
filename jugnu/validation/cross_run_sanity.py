from __future__ import annotations


def sanity_check(
    new_records: list[dict],
    previous_records: list[dict],
    min_retention_ratio: float = 0.5,
) -> tuple[bool, str]:
    """Warn if new run returns far fewer records than previous. No hardcoded field names."""
    if not previous_records:
        return True, "no_baseline"
    if not new_records:
        return False, "empty_vs_baseline"
    ratio = len(new_records) / len(previous_records)
    if ratio < min_retention_ratio:
        return False, f"record_count_drop: {len(new_records)} vs {len(previous_records)}"
    return True, "ok"
