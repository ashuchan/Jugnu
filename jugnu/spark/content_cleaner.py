"""html_to_fit_markdown(), chunk_content() — reduce HTML tokens before LLM.

Raw HTML is NEVER sent to Prompt-2. Always run html_to_fit_markdown() first.
Implemented in Phase 5.
"""
from __future__ import annotations
