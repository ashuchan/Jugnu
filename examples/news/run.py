"""Example runner for news skill."""
from __future__ import annotations

import asyncio

from jugnu.contracts import CrawlInput
from jugnu.crawler import Jugnu
from jugnu.observability.metrics import CrawlMetrics
from jugnu.reporting.run_report import build_run_report

from examples.news.skill import news_skill


async def main() -> None:
    jugnu = Jugnu(skill=news_skill)
    memory = await jugnu.warm_up()
    print(f"Warm-up complete. Cost: ${memory.warmup_cost_usd:.4f}")

    urls = {
        "https://www.bbc.com/news": CrawlInput(url="https://www.bbc.com/news"),
        "https://www.reuters.com/world/": CrawlInput(url="https://www.reuters.com/world/"),
        "https://apnews.com/hub/business": CrawlInput(url="https://apnews.com/hub/business"),
    }

    results = await jugnu.crawl(urls)
    metrics = CrawlMetrics.from_results(results, skill_name=news_skill.name)
    print(metrics.summary())
    print(build_run_report(results, skill_name=news_skill.name, memory=memory))


if __name__ == "__main__":
    asyncio.run(main())
