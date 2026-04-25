"""Health-scored proxy pool.

Per design: bumps health by ±0.05 on success / ±0.25 on failure, quarantines
proxies that drop below 0.25, and prefers the highest-health proxy on each
selection. Backwards-compatible with the old simple `next()` round-robin API.
"""
from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass


@dataclass
class _ProxyState:
    url: str
    health: float = 1.0
    quarantined: bool = False


class ProxyPool:
    def __init__(self, proxies: list[str] | None = None) -> None:
        self._states: list[_ProxyState] = [_ProxyState(url=p) for p in (proxies or [])]
        self._lock = threading.Lock()
        self._cycle = (
            itertools.cycle(self._states) if self._states else None
        )  # backwards compat

    # --- new health-scored interface --------------------------------------------------
    def select(self) -> str | None:
        """Return the healthiest non-quarantined proxy, or None if pool is empty."""
        with self._lock:
            live = [s for s in self._states if not s.quarantined]
            if not live:
                return None
            best = max(live, key=lambda s: s.health)
            return best.url

    def report_success(self, proxy_url: str) -> None:
        self._adjust(proxy_url, +0.05)

    def report_failure(self, proxy_url: str, severity: str = "soft") -> None:
        delta = -0.25 if severity == "hard" else -0.05
        self._adjust(proxy_url, delta)

    def health(self, proxy_url: str) -> float:
        with self._lock:
            for s in self._states:
                if s.url == proxy_url:
                    return s.health
        return 0.0

    def is_quarantined(self, proxy_url: str) -> bool:
        with self._lock:
            for s in self._states:
                if s.url == proxy_url:
                    return s.quarantined
        return False

    # --- legacy round-robin interface -------------------------------------------------
    def next(self) -> str | None:
        if self._cycle is None:
            return None
        try:
            return next(self._cycle).url
        except StopIteration:
            return None

    def is_empty(self) -> bool:
        return len(self._states) == 0

    def size(self) -> int:
        return len(self._states)

    # --- internal --------------------------------------------------------------------
    def _adjust(self, proxy_url: str, delta: float) -> None:
        with self._lock:
            for state in self._states:
                if state.url == proxy_url:
                    state.health = max(0.0, min(1.0, state.health + delta))
                    if state.health < 0.25:
                        state.quarantined = True
                    elif state.health >= 0.5:
                        state.quarantined = False
                    return
