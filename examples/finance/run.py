"""Example runner for finance skill."""
from __future__ import annotations

import asyncio

from jugnu.contracts import CrawlInput
from jugnu.crawler import Jugnu
from jugnu.observability.metrics import CrawlMetrics
from jugnu.reporting.run_report import build_run_report

from examples.finance.skill import finance_skill


async def main() -> None:
    jugnu = Jugnu(skill=finance_skill)
    memory = await jugnu.warm_up()
    print(f"Warm-up complete. Cost: ${memory.warmup_cost_usd:.4f}")

    urls = {
        "https://finance.yahoo.com/quote/AAPL": CrawlInput(
            url="https://finance.yahoo.com/quote/AAPL"
        ),
        "https://www.marketwatch.com/investing/stock/msft": CrawlInput(
            url="https://www.marketwatch.com/investing/stock/msft"
        ),
        "https://www.nasdaq.com/market-activity/stocks/googl": CrawlInput(
            url="https://www.nasdaq.com/market-activity/stocks/googl"
        ),
    }

    results = await jugnu.crawl(urls)
    metrics = CrawlMetrics.from_results(results, skill_name=finance_skill.name)
    print(metrics.summary())
    print(build_run_report(results, skill_name=finance_skill.name, memory=memory))


if __name__ == "__main__":
    asyncio.run(main())
