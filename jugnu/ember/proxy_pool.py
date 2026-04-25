from __future__ import annotations

import itertools


class ProxyPool:
    """Round-robin proxy pool. Returns None when pool is empty."""

    def __init__(self, proxies: list[str] | None = None) -> None:
        self._proxies = proxies or []
        self._cycle = itertools.cycle(self._proxies) if self._proxies else None

    def next(self) -> str | None:
        if self._cycle is None:
            return None
        try:
            return next(self._cycle)
        except StopIteration:
            return None

    def is_empty(self) -> bool:
        return len(self._proxies) == 0

    def size(self) -> int:
        return len(self._proxies)
