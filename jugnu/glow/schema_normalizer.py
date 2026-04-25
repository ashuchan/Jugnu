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
