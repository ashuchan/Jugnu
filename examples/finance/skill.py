"""Financial data crawler example Skill."""
from __future__ import annotations

from jugnu.skill import JugnuSettings, OutputSchema, Skill, SourceHint

finance_skill = Skill(
    name="finance_data",
    version="1.0.0",
    description="Extract financial instrument data including ticker, price, volume, market cap.",
    output_schema=OutputSchema(
        fields=["ticker", "name", "price", "change_pct", "volume", "market_cap", "sector"],
        primary_key="ticker",
        merging_keys=["ticker", "name"],
        minimum_fields=["ticker", "price"],
    ),
    source_hints=[
        SourceHint(
            link_keywords=["stock", "equity", "fund", "etf", "quote", "market"],
            api_patterns=["/api/quotes", "/v1/markets", "/stocks/", "/market-data/"],
        )
    ],
    jugnu_settings=JugnuSettings(
        link_confidence_threshold=0.5,
        max_concurrent_crawls=3,
        carry_forward_on_failure=True,
    ),
)
