"""Example runner for sports skill."""
from __future__ import annotations

import asyncio

from jugnu.contracts import CrawlInput
from jugnu.crawler import Jugnu
from jugnu.observability.metrics import CrawlMetrics
from jugnu.reporting.run_report import build_run_report

from examples.sports.skill import sports_skill


async def main() -> None:
    jugnu = Jugnu(skill=sports_skill)
    memory = await jugnu.warm_up()
    print(f"Warm-up complete. Cost: ${memory.warmup_cost_usd:.4f}")

    urls = {
        "https://www.espn.com/nba/standings": CrawlInput(
            url="https://www.espn.com/nba/standings"
        ),
        "https://www.espn.com/nfl/standings": CrawlInput(
            url="https://www.espn.com/nfl/standings"
        ),
        "https://www.espn.com/soccer/standings": CrawlInput(
            url="https://www.espn.com/soccer/standings"
        ),
    }

    results = await jugnu.crawl(urls)
    metrics = CrawlMetrics.from_results(results, skill_name=sports_skill.name)
    print(metrics.summary())
    print(build_run_report(results, skill_name=sports_skill.name, memory=memory))


if __name__ == "__main__":
    asyncio.run(main())
