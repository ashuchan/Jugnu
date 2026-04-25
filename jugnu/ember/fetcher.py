from __future__ import annotations

import asyncio
import time

from jugnu.contracts import FetchResult
from jugnu.ember.captcha_detect import is_captcha_page
from jugnu.ember.rate_limiter import RateLimiter
from jugnu.ember.stealth import StealthConfig

_DEFAULT_TIMEOUT = 30_000  # ms


class Ember:
    """Async fetch layer — never raises, always returns FetchResult."""

    def __init__(
        self,
        stealth: StealthConfig | None = None,
        rate_limiter: RateLimiter | None = None,
        proxy: str | None = None,
        timeout_ms: int = _DEFAULT_TIMEOUT,
        max_retries: int = 2,
    ) -> None:
        self._stealth = stealth or StealthConfig()
        self._rate_limiter = rate_limiter or RateLimiter()
        self._proxy = proxy
        self._timeout_ms = timeout_ms
        self._max_retries = max_retries
        self._browser: object | None = None
        self._playwright: object | None = None

    async def __aenter__(self) -> Ember:
        await self._start_browser()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._close_browser()

    async def fetch(self, url: str, screenshot: bool = False) -> FetchResult:
        """Fetch a URL, retrying up to max_retries times. Never raises."""
        last_error: str | None = None
        for attempt in range(self._max_retries + 1):
            if attempt > 0:
                await asyncio.sleep(2 ** attempt)
            try:
                await self._rate_limiter.acquire(url)
                result = await self._fetch_once(url, screenshot=screenshot)
                if result.success:
                    return result
                last_error = f"HTTP {result.status_code}"
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
        return FetchResult(url=url, status_code=0, error=last_error or "unknown error")

    async def _fetch_once(self, url: str, screenshot: bool = False) -> FetchResult:
        try:
            import playwright.async_api  # noqa: PLC0415, F401
        except ImportError:
            return await self._fetch_httpx(url)

        if self._playwright is None:
            return await self._fetch_httpx(url)

        start = time.monotonic()
        page = None
        try:
            ua, headers = self._stealth.for_url(url)
            context = await self._browser.new_context(  # type: ignore[union-attr]
                user_agent=ua,
                extra_http_headers=headers,
                proxy={"server": self._proxy} if self._proxy else None,
            )
            page = await context.new_page()
            response = await page.goto(
                url, timeout=self._timeout_ms, wait_until="domcontentloaded"
            )
            await self._stealth.apply_evasions(page)
            html = await page.content()
            status_code = response.status if response else 0
            headers = dict(response.headers) if response else {}
            shot: bytes | None = None
            if screenshot:
                shot = await page.screenshot(full_page=True)
            latency = (time.monotonic() - start) * 1000
            blocked = is_captcha_page(html)
            return FetchResult(
                url=url,
                status_code=status_code if not blocked else 403,
                html=html,
                content_type=headers.get("content-type", ""),
                response_headers=headers,
                latency_ms=latency,
                error="captcha_detected" if blocked else None,
                screenshot=shot,
            )
        except Exception as exc:  # noqa: BLE001
            return FetchResult(url=url, status_code=0, error=str(exc))
        finally:
            if page is not None:
                await page.close()

    async def _fetch_httpx(self, url: str) -> FetchResult:
        import httpx  # noqa: PLC0415

        start = time.monotonic()
        try:
            ua, headers = self._stealth.for_url(url)
            request_headers = {"User-Agent": ua, **headers}
            async with httpx.AsyncClient(
                timeout=self._timeout_ms / 1000,
                headers=request_headers,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
                latency = (time.monotonic() - start) * 1000
                html = resp.text
                blocked = is_captcha_page(html)
                return FetchResult(
                    url=url,
                    status_code=resp.status_code if not blocked else 403,
                    html=html,
                    text=html,
                    content_type=resp.headers.get("content-type", ""),
                    response_headers=dict(resp.headers),
                    latency_ms=latency,
                    error="captcha_detected" if blocked else None,
                )
        except Exception as exc:  # noqa: BLE001
            return FetchResult(url=url, status_code=0, error=str(exc))

    async def _start_browser(self) -> None:
        try:
            from playwright.async_api import async_playwright  # noqa: PLC0415

            self._playwright = await async_playwright().start()
            launch_opts: dict = {"headless": True}
            if self._proxy:
                launch_opts["proxy"] = {"server": self._proxy}
            self._browser = await self._playwright.chromium.launch(**launch_opts)
        except Exception:  # noqa: BLE001
            self._playwright = None
            self._browser = None

    async def _close_browser(self) -> None:
        try:
            if self._browser:
                await self._browser.close()  # type: ignore[attr-defined]
            if self._playwright:
                await self._playwright.stop()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._browser = None
            self._playwright = None
