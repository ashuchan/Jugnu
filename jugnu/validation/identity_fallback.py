from __future__ import annotations

import hashlib
import json


def assign_identity(record: dict, primary_key: str | None = None) -> dict:
    """Add a stable _id to a record if primary_key is missing or None."""
    if primary_key and primary_key in record and record[primary_key]:
        return record
    # Build synthetic identity from sorted record content
    content = json.dumps(record, sort_keys=True, default=str)
    synthetic_id = hashlib.sha256(content.encode()).hexdigest()[:16]
    return {**record, "_id": synthetic_id}


def assign_identities(
    records: list[dict],
    primary_key: str | None = None,
) -> list[dict]:
    return [assign_identity(r, primary_key) for r in records]
