from __future__ import annotations

from abc import ABC, abstractmethod

from jugnu.contracts import AdapterResult, FetchResult


class BaseAdapter(ABC):
    name: str = "base"
    tier: int = 99

    @abstractmethod
    async def can_handle(self, fetch_result: FetchResult) -> bool:
        ...

    @abstractmethod
    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        ...
