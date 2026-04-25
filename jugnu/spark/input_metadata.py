from __future__ import annotations

import json


def render_input_metadata(metadata: dict | None) -> str:
    """Render a CrawlInput.metadata dict as a prompt-friendly block.

    Empty metadata → "(none provided)". Non-empty → pretty JSON the LLM can read.
    """
    if not metadata:
        return "(none provided)"
    try:
        return json.dumps(metadata, indent=2, default=str, sort_keys=True)
    except (TypeError, ValueError):
        return str(metadata)


def render_negative_keywords(keywords: list[str] | None) -> str:
    if not keywords:
        return "(none)"
    return ", ".join(str(k) for k in keywords)
