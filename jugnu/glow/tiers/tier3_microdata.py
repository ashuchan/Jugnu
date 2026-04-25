from __future__ import annotations

from bs4 import BeautifulSoup

from jugnu.contracts import AdapterResult, FetchResult
from jugnu.glow.base_adapter import BaseAdapter


class MicrodataAdapter(BaseAdapter):
    name = "microdata"
    tier = 3

    async def can_handle(self, fetch_result: FetchResult) -> bool:
        return "itemscope" in fetch_result.html or "itemtype" in fetch_result.html

    async def extract(self, fetch_result: FetchResult, schema_fields: list[str]) -> AdapterResult:
        records: list[dict] = []
        try:
            soup = BeautifulSoup(fetch_result.html, "lxml")
            for item in soup.find_all(attrs={"itemscope": True}):
                record: dict = {}
                for prop in item.find_all(attrs={"itemprop": True}):
                    name = prop.get("itemprop", "")
                    value = prop.get("content") or prop.get_text(strip=True)
                    if name:
                        record[name] = value
                if record:
                    records.append(record)
        except Exception:  # noqa: BLE001
            pass
        return AdapterResult(
            records=records,
            tier_used=self.name,
            confidence=0.75 if records else 0.0,
        )
