from __future__ import annotations

import re

_NOISE_TAGS = re.compile(
    r"<(script|style|nav|footer|header|aside|iframe|noscript)(\s[^>]*)?>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_HTML_COMMENTS = re.compile(r"<!--.*?-->", re.DOTALL)
_MULTI_BLANK = re.compile(r"\n{3,}")
_MAX_MARKDOWN_CHARS = 12_000


def html_to_fit_markdown(html: str, max_chars: int = _MAX_MARKDOWN_CHARS) -> str:
    """Convert HTML to clean markdown, trimmed to max_chars. Never raises."""
    try:
        import markdownify  # noqa: PLC0415

        clean = _HTML_COMMENTS.sub("", html)
        clean = _NOISE_TAGS.sub("", clean)
        md: str = markdownify.markdownify(clean, heading_style="ATX", strip=["a"])
        md = _MULTI_BLANK.sub("\n\n", md).strip()
        if len(md) > max_chars:
            md = md[:max_chars] + "\n...[truncated]"
        return md
    except Exception:  # noqa: BLE001
        # Fallback: strip all tags
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r" {2,}", " ", text).strip()
        return text[:max_chars]


def strip_html_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)
