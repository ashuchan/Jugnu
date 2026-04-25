from __future__ import annotations

from typing import Any

from jugnu.skill import OutputSchema

try:
    from jsonschema import Draft202012Validator
    from jsonschema.exceptions import SchemaError
except ImportError:  # pragma: no cover
    Draft202012Validator = None
    SchemaError = Exception


def passes_schema_gate(
    records: list[dict],
    schema: OutputSchema,
) -> tuple[bool, str]:
    """Return (passes, reason). No hardcoded field names — uses schema.minimum_fields.

    Two checks, in order:
      1. minimum_fields presence — at least 50% of records carry every required field.
      2. OutputSchema.json_schema validation (per-record) — at least 50% of
         records validate against the rich schema (bounds, patterns, types).
         Skipped silently if jsonschema is unavailable or schema is empty.
    """
    if not records:
        return False, "no_records"
    valid_min = 0
    for record in records:
        keys = set(record.keys())
        if all(mf in keys for mf in schema.minimum_fields):
            valid_min += 1
    min_ratio = valid_min / len(records)
    if min_ratio < 0.5:
        return False, f"insufficient_fields: {min_ratio:.0%} records have minimum fields"

    # Optional richer validation against OutputSchema.json_schema. Per-record
    # because Prompt-2 returns a flat list of records, even when the schema
    # describes a single object — we treat the schema as the per-record shape.
    json_schema = schema.json_schema
    if not json_schema or Draft202012Validator is None:
        return True, "ok"
    record_schema = _per_record_schema(json_schema)
    if not record_schema:
        return True, "ok"
    try:
        validator = Draft202012Validator(record_schema)
    except SchemaError:
        return True, "ok_invalid_schema_skipped"
    json_valid = sum(1 for r in records if not list(validator.iter_errors(r)))
    json_ratio = json_valid / len(records)
    if json_ratio < 0.5:
        return False, f"insufficient_json_schema_pass: {json_ratio:.0%} records pass json_schema"
    return True, "ok"


def _per_record_schema(schema: dict[str, Any]) -> dict[str, Any] | None:
    """Best-effort: if the OutputSchema.json_schema describes an array,
    return its `items`; otherwise assume it already describes a single record.
    """
    if not isinstance(schema, dict):
        return None
    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        items: dict[str, Any] = schema["items"]
        return items
    return schema


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
