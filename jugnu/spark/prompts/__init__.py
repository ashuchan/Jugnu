from __future__ import annotations

from functools import cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@cache
def load_template(name: str) -> str:
    """Load a prompt template by file name (without .txt extension).

    Templates live in jugnu/spark/prompts/<name>.txt and use {placeholders}
    that callers fill via str.format(**kwargs).
    """
    path = _PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8")


def render_template(name: str, **kwargs: object) -> str:
    """Load a template and substitute placeholders. Missing keys are tolerated
    (kept as `{placeholder}` literals) so callers can layer substitutions."""
    template = load_template(name)
    return _safe_format(template, kwargs)


def _safe_format(template: str, mapping: dict[str, object]) -> str:
    class _MissingDict(dict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    return template.format_map(_MissingDict(**mapping))
