from __future__ import annotations

import json

from jugnu.spark.input_metadata import render_input_metadata, render_negative_keywords
from jugnu.spark.prompts import render_template
from jugnu.spark.provider import LLMProvider
from jugnu.spark.skill_memory import SkillMemory


class MergeLLM:
    """Prompt-3: Match new records to existing records from a prior crawl.

    Returns a dict with `merge_decisions` describing which new records map to
    existing ones (update) vs. which are genuinely new (insert), plus the
    reconciled `merged_records` list. Per spec, Prompt-3 does NOT emit an
    improvement_signal — merge decisions are not domain learning.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    async def merge(
        self,
        existing_records: list[dict],
        new_records: list[dict],
        primary_key: str | None,
        merging_keys: list[str],
        general_instructions: str = "",
        memory: SkillMemory | None = None,
        url: str = "",
        skill_name: str = "",
        output_fields: list[str] | None = None,
        minimum_fields: list[str] | None = None,
        input_metadata: dict | None = None,
        negative_keywords: list[str] | None = None,
    ) -> dict:
        if not new_records:
            return _passthrough(existing_records, new_records, response_cost=0.0)
        if not existing_records:
            # No prior data → all new records are inserts; no LLM needed.
            return {
                "merge_decisions": [
                    {
                        "new_record_index": i,
                        "existing_record_id": None,
                        "merge": False,
                        "reason": "no_prior_records",
                    }
                    for i in range(len(new_records))
                ],
                "merged_records": list(new_records),
                "added_count": len(new_records),
                "updated_count": 0,
                "cost_usd": 0.0,
                "error": None,
            }

        fields = list(output_fields or [])
        synonyms = (memory.confirmed_field_synonyms if memory else {}) or {}
        field_hints = (memory.field_extraction_hints if memory else {}) or {}
        if fields:
            synonyms = {k: v for k, v in synonyms.items() if k in fields}
            field_hints = {k: v for k, v in field_hints.items() if k in fields}

        prompt = render_template(
            "merge",
            general_instructions=general_instructions or "(no instructions provided)",
            output_fields=", ".join(fields) or "(none)",
            minimum_fields=", ".join(minimum_fields or []) or "(none)",
            primary_key=primary_key or "(none)",
            merging_keys=", ".join(merging_keys) if merging_keys else "(none)",
            confirmed_field_synonyms_json=json.dumps(synonyms, indent=2, default=str),
            field_extraction_hints_json=json.dumps(field_hints, indent=2, default=str),
            existing_records_json=json.dumps(existing_records[:50], indent=2, default=str),
            new_records_json=json.dumps(new_records[:50], indent=2, default=str),
            input_metadata=render_input_metadata(input_metadata),
            negative_keywords=render_negative_keywords(negative_keywords),
        )
        response = await self._provider.complete(
            [{"role": "user", "content": prompt}],
            stage="prompt3_merge",
            url=url,
            skill=skill_name,
        )
        return _parse_merge(response, existing_records, new_records, primary_key, merging_keys)


def _parse_merge(
    response: dict,
    existing: list[dict],
    new_records: list[dict],
    primary_key: str | None,
    merging_keys: list[str],
) -> dict:
    cost = float(response.get("cost_usd") or 0.0)
    if response.get("error"):
        return _passthrough(existing, new_records, response_cost=cost, error=response.get("error"))
    try:
        data = json.loads(response.get("content") or "")
    except json.JSONDecodeError:
        return _passthrough(existing, new_records, response_cost=cost, error="invalid_json")

    decisions = data.get("merge_decisions") or []
    merged, added, updated = _apply_decisions(
        existing, new_records, decisions, primary_key, merging_keys
    )
    return {
        "merge_decisions": decisions,
        "merged_records": merged,
        "added_count": added,
        "updated_count": updated,
        "cost_usd": cost,
        "error": None,
    }


def _apply_decisions(
    existing: list[dict],
    new_records: list[dict],
    decisions: list[dict],
    primary_key: str | None,
    merging_keys: list[str],
) -> tuple[list[dict], int, int]:
    by_id = {_record_id(r, primary_key, merging_keys): dict(r) for r in existing}
    added = 0
    updated = 0
    for decision in decisions:
        idx = decision.get("new_record_index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(new_records):
            continue
        new_rec = new_records[idx]
        existing_id = decision.get("existing_record_id")
        if decision.get("merge") and existing_id and existing_id in by_id:
            by_id[existing_id].update(new_rec)
            updated += 1
        else:
            new_id = _record_id(new_rec, primary_key, merging_keys) or f"_new_{idx}"
            by_id[new_id] = dict(new_rec)
            added += 1
    return list(by_id.values()), added, updated


def _record_id(record: dict, primary_key: str | None, merging_keys: list[str]) -> str:
    if primary_key and record.get(primary_key) not in (None, ""):
        return str(record[primary_key])
    parts = [str(record.get(k, "")) for k in merging_keys]
    return "::".join(parts) if any(parts) else ""


def _passthrough(
    existing: list[dict],
    new_records: list[dict],
    response_cost: float,
    error: str | None = None,
) -> dict:
    return {
        "merge_decisions": [],
        "merged_records": list(existing) + list(new_records),
        "added_count": len(new_records),
        "updated_count": 0,
        "cost_usd": response_cost,
        "error": error,
    }
