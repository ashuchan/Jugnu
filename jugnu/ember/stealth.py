from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0",
]

_ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.8,en-GB;q=0.6",
    "en-GB,en;q=0.9,en-US;q=0.8",
]

_EVASION_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
    Object.defineProperty(window, 'chrome', {get: () => ({runtime: {}})});
"""


@dataclass(frozen=True)
class Identity:
    user_agent: str
    accept_language: str

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept-Language": self.accept_language,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
        }


class IdentityPool:
    """Deterministic 8-identity pool keyed by SHA256(url).

    Same URL always maps to the same identity within a pool — useful for
    cookie/session continuity across retries — but two different URLs spread
    across the pool, so we don't look like a single client hammering a host.
    """

    def __init__(self, identities: list[Identity] | None = None) -> None:
        if identities:
            self._identities = list(identities)
        else:
            n_lang = len(_ACCEPT_LANGUAGES)
            self._identities = [
                Identity(user_agent=ua, accept_language=_ACCEPT_LANGUAGES[i % n_lang])
                for i, ua in enumerate(_USER_AGENTS)
            ]

    def select(self, url: str) -> Identity:
        if not self._identities:
            return Identity(user_agent=_USER_AGENTS[0], accept_language=_ACCEPT_LANGUAGES[0])
        digest = hashlib.sha256(url.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % len(self._identities)
        return self._identities[index]

    def size(self) -> int:
        return len(self._identities)


class StealthConfig:
    """Per-fetch stealth context. Backwards-compatible with the old single-UA shim."""

    def __init__(
        self,
        user_agent: str | None = None,
        extra_headers: dict[str, str] | None = None,
        identity_pool: IdentityPool | None = None,
    ) -> None:
        self._pool = identity_pool or IdentityPool()
        if user_agent is not None:
            self.user_agent = user_agent
        else:
            self.user_agent = self._pool.select("").user_agent
        self.extra_headers: dict[str, str] = extra_headers or {
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            ),
        }

    def for_url(self, url: str) -> tuple[str, dict[str, str]]:
        identity = self._pool.select(url)
        headers = dict(self.extra_headers)
        headers.update(identity.headers)
        return identity.user_agent, headers

    async def apply_evasions(self, page: Page) -> None:
        try:
            await page.add_init_script(_EVASION_SCRIPT)
        except Exception:  # noqa: BLE001
            pass
