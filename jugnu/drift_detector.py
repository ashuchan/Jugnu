from __future__ import annotations

import hashlib
from typing import Optional

from jugnu.profile import ScrapeProfile


def compute_page_fingerprint(html: str) -> str:
    return hashlib.sha256(html.encode()).hexdigest()[:32]


def detect_schema_drift(
    profile: ScrapeProfile,
    current_fingerprint: str,
) -> bool:
    """Return True if the page fingerprint changed significantly from profile baseline."""
    stored = profile.fingerprint_hash
    if stored is None:
        return False
    return stored != current_fingerprint


def update_fingerprint(profile: ScrapeProfile, html: str) -> ScrapeProfile:
    profile.fingerprint_hash = compute_page_fingerprint(html)
    return profile
