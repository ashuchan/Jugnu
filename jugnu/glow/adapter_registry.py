from __future__ import annotations

from jugnu.glow.base_adapter import BaseAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: list[BaseAdapter] = []

    def register(self, adapter: BaseAdapter) -> None:
        self._adapters.append(adapter)
        self._adapters.sort(key=lambda a: a.tier)

    def all_adapters(self) -> list[BaseAdapter]:
        return list(self._adapters)

    def by_tier(self, tier: int) -> list[BaseAdapter]:
        return [a for a in self._adapters if a.tier == tier]
