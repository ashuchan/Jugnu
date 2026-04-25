from __future__ import annotations

import re


def normalize_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", raw.lower().strip()).strip("_")


def normalize_record(record: dict, field_aliases: dict[str, list[str]] | None = None) -> dict:
    normalized: dict = {}
    aliases = field_aliases or {}
    reverse: dict[str, str] = {}
    for canonical, synonyms in aliases.items():
        for s in synonyms:
            reverse[normalize_key(s)] = canonical
        reverse[normalize_key(canonical)] = canonical

    for raw_key, value in record.items():
        key = normalize_key(raw_key)
        canonical = reverse.get(key, key)
        normalized[canonical] = value
    return normalized


def filter_to_schema(record: dict, fields: list[str]) -> dict:
    return {k: v for k, v in record.items() if k in fields}


def record_matches_negative_keyword(record: dict, negative_keywords: list[str] | None) -> bool:
    """True if any string-typed field value contains a negative_keyword as a substring.

    Walks shallowly through dicts and one level of lists so nested arrays of
    strings (e.g. amenities) are also checked.
    """
    if not negative_keywords or not isinstance(record, dict):
        return False
    for value in record.values():
        if _value_matches(value, negative_keywords):
            return True
    return False


def _value_matches(value: object, negative_keywords: list[str]) -> bool:
    if isinstance(value, str):
        return any(kw and kw in value for kw in negative_keywords)
    if isinstance(value, list):
        return any(_value_matches(v, negative_keywords) for v in value)
    if isinstance(value, dict):
        return any(_value_matches(v, negative_keywords) for v in value.values())
    return False


def filter_records_by_negative_keywords(
    records: list[dict],
    negative_keywords: list[str] | None,
) -> list[dict]:
    """Drop records that contain any negative_keyword substring in any string value.

    Final safety net after LLM-side filtering — guarantees junk like 'MODULE_*'
    cannot reach the caller even if the model ignored the prompt instruction.
    """
    if not negative_keywords:
        return records
    return [r for r in records if not record_matches_negative_keyword(r, negative_keywords)]
