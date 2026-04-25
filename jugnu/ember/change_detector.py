from __future__ import annotations

import hashlib


def content_fingerprint(html: str) -> str:
    return hashlib.sha256(html.encode()).hexdigest()[:32]


def has_content_changed(html: str, previous_fingerprint: str) -> bool:
    return content_fingerprint(html) != previous_fingerprint
