from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse


class RateLimiter:
    """Per-domain token bucket rate limiter."""

    def __init__(self, requests_per_second: float = 1.0, burst: int = 3) -> None:
        self._rps = max(requests_per_second, 0.01)
        self._burst = max(burst, 1)
        self._tokens: dict[str, float] = {}
        self._last_time: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc or url
        except Exception:  # noqa: BLE001
            return url

    async def acquire(self, url: str) -> None:
        domain = self._domain(url)
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()
            self._tokens[domain] = float(self._burst)
            self._last_time[domain] = time.monotonic()

        async with self._locks[domain]:
            now = time.monotonic()
            elapsed = now - self._last_time[domain]
            self._tokens[domain] = min(
                self._burst,
                self._tokens[domain] + elapsed * self._rps,
            )
            self._last_time[domain] = now
            if self._tokens[domain] >= 1.0:
                self._tokens[domain] -= 1.0
            else:
                wait = (1.0 - self._tokens[domain]) / self._rps
                await asyncio.sleep(wait)
                self._tokens[domain] = 0.0
