"""Crystallizer — turn Prompt-2 field_mappings into a ScrapeProfile update.

Prompt-2 returns `field_mappings` of the form:
    {
      "api": {"url_pattern": "...", "json_paths": {...}, "response_envelope": "..."},
      "dom": {"container": "...", "selectors": {...}}
    }

This module materialises those into the profile's ApiHints + DomHints +
field_mappings list so future runs can replay deterministically (Tier 1a).
"""
from __future__ import annotations

from datetime import UTC, datetime

from jugnu.profile import LlmFieldMapping, ScrapeProfile


def crystallize(
    profile: ScrapeProfile,
    field_mappings: dict | None,
    field_mapping_notes: str = "",
) -> ScrapeProfile:
    """Mutate `profile` in place with the field_mappings from a Prompt-2 result.

    Returns the profile for fluency. No-op if `field_mappings` is None/empty.
    Never raises — silently ignores malformed shapes.
    """
    if not field_mappings or not isinstance(field_mappings, dict):
        return profile

    api_block = field_mappings.get("api") or {}
    dom_block = field_mappings.get("dom") or {}
    timestamp = datetime.now(UTC).isoformat()

    if isinstance(api_block, dict):
        url_pattern = api_block.get("url_pattern")
        if url_pattern and url_pattern not in profile.api_hints.confirmed_patterns:
            profile.api_hints.confirmed_patterns.append(url_pattern)
        envelope = api_block.get("response_envelope")
        if envelope and not profile.api_hints.response_format:
            profile.api_hints.response_format = str(envelope)
        json_paths = api_block.get("json_paths") or {}
        if isinstance(json_paths, dict):
            for field, path in json_paths.items():
                _upsert_mapping(
                    profile,
                    field,
                    hint=str(path),
                    note=field_mapping_notes,
                    ts=timestamp,
                )

    if isinstance(dom_block, dict):
        container = dom_block.get("container")
        if container and container not in profile.dom_hints.list_container_selectors:
            profile.dom_hints.list_container_selectors.append(str(container))
        selectors = dom_block.get("selectors") or {}
        if isinstance(selectors, dict):
            for field, css in selectors.items():
                profile.dom_hints.confirmed_selectors[str(field)] = str(css)
                _upsert_mapping(
                    profile,
                    field,
                    hint=str(css),
                    note=field_mapping_notes,
                    ts=timestamp,
                )

    profile.updated_at = timestamp
    return profile


def _upsert_mapping(
    profile: ScrapeProfile,
    field_name: str,
    hint: str,
    note: str,
    ts: str,
) -> None:
    for mapping in profile.field_mappings:
        if mapping.field_name == field_name:
            mapping.extraction_hint = hint
            mapping.last_seen = ts
            if note and note not in mapping.synonyms:
                mapping.synonyms.append(note)
            return
    profile.field_mappings.append(
        LlmFieldMapping(
            field_name=str(field_name),
            extraction_hint=hint,
            synonyms=[note] if note else [],
            confidence=0.7,
            last_seen=ts,
        )
    )
