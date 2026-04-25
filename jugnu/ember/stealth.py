from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_EVASION_SCRIPT = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
"""


class StealthConfig:
    def __init__(
        self,
        user_agent: str = _DEFAULT_UA,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.extra_headers: dict[str, str] = extra_headers or {
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    async def apply_evasions(self, page: "Page") -> None:
        try:
            await page.add_init_script(_EVASION_SCRIPT)
        except Exception:  # noqa: BLE001
            pass
