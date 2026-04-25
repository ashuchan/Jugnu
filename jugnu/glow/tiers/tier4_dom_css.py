from __future__ import annotations

from bs4 import BeautifulSoup

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter


class DomCssAdapter(BaseAdapter):
    name = "dom_css"
    tier = 4

    def __init__(self, selectors: dict[str, str] | None = None) -> None:
        self._selectors = selectors or {}

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        return bool(self._selectors) and bool(fetch_result.html)

    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        records: list[dict] = []
        try:
            soup = BeautifulSoup(fetch_result.html, "lxml")
            record: dict = {}
            for field, selector in self._selectors.items():
                el = soup.select_one(selector)
                if el:
                    record[field] = el.get_text(strip=True)
            if record:
                records.append(record)
        except Exception:  # noqa: BLE001
            pass
        return AdapterResult(
            records=records,
            tier_used=self.name,
            confidence=0.6 if records else 0.0,
        )
