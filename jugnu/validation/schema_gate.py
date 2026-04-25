from __future__ import annotations

from jugnu.skill import OutputSchema


def passes_schema_gate(
    records: list[dict],
    schema: OutputSchema,
) -> tuple[bool, str]:
    """Return (passes, reason). No hardcoded field names — uses schema.minimum_fields."""
    if not records:
        return False, "no_records"
    valid = 0
    for record in records:
        keys = set(record.keys())
        if all(mf in keys for mf in schema.minimum_fields):
            valid += 1
    ratio = valid / len(records)
    if ratio < 0.5:
        return False, f"insufficient_fields: {ratio:.0%} records have minimum fields"
    return True, "ok"


def validate_primary_key_uniqueness(
    records: list[dict],
    primary_key: str | None,
) -> tuple[bool, str]:
    if not primary_key:
        return True, "no_primary_key"
    seen: set = set()
    for r in records:
        val = r.get(primary_key)
        if val is None:
            continue
        if val in seen:
            return False, f"duplicate_primary_key: {val}"
        seen.add(val)
    return True, "ok"
